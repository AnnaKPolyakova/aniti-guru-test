# Техническая документация: классы и модули

Краткое описание модулей и классов проекта и их ответственности.

---

## Точки входа

| Компонент | Файл | Назначение |
|-----------|------|------------|
| HTTP API | `src/app/__main__.py` | Запуск приложения через `python -m src.app` или uvicorn; создаёт приложение через `create_app(settings.TEST)`. |
| Фабрика приложения | `src/app/main.py` | `create_app(test: bool)` — создаёт FastAPI-приложение, подключает lifespan (Postgres, Redis), подключает роутеры auth и payments. |
| Celery | `src.app.celery` | Приложение Celery: broker/backend из Redis, автоподключение задач из `src.app.tasks`, расписание beat (проверка платежей каждые 3 часа). |
| Миграции | `alembic/env.py` | URL БД из `Settings`, `target_metadata = db_models.Base.metadata`. |

---

## API (роутеры)

### `src.app.api.auth`

- **`auth_router`** — префикс `/auth`, тег `auth`.
- **`FastAPIUsers`** (`fastapi_users`) — основной бэкенд аутентификации (JWT).
- **`FastAPIUsers`** (`fastapi_users_refresh`) — для refresh-токена из cookie.
- Маршруты: JWT login, регистрация, CRUD пользователей, `POST /auth/jwt/refresh`, `POST /auth/jwt/logout_refresh`.

### `src.app.api.payment`

- **`deposit_acquiring_router`** — префикс `/payments`.
- **`create_acquiring_deposit_payment`** — `POST /payments/deposit/acquiring`: создание платежа пополнения через эквайринг; использует `PaymentService`, обрабатывает `OrderNotFoundError`, `OverpaymentError`, `ForbiddenOrderAccessError`, `AcquiringStartError`.
- **`create_return_payment`** — `POST /payments/return`: создание возврата; использует `ReturnPaymentService`, обрабатывает `OrderNotFoundError`, `ReturnAmountExceedsBalanceError`, `ForbiddenOrderAccessError`.

---

## Сервисы

### `src.app.services.users`

- **`JWTStrategyWithBlacklist`** — JWT-стратегия с учётом чёрного списка: при чтении токена проверяет таблицу `revoked_tokens`; при выходе добавляет токен в чёрный список.
- **`get_user_db`** — зависимость FastAPI, возвращает `SQLAlchemyUserDatabase(session, UserORM)`.
- **`UserManager`** — менеджер пользователей FastAPI-Users (валидация пароля, создание и т.д.).
- **`auth_backend`** — бэкенд аутентификации (Bearer + JWT с blacklist).
- **`refresh_backend`** — бэкенд для refresh (Cookie transport, та же JWT-стратегия).

### `src.app.services.payment`

- **`PaymentService`** (`payment_service.py`) — создание платежа пополнения через эквайринг:
  - `_get_order_for_update()` — заказ по id с блокировкой; при отсутствии — `OrderNotFoundError`.
  - `_check_order_belongs_to_user()` — иначе `ForbiddenOrderAccessError`.
  - `_get_current_order_balance()` — баланс по заказу (депозиты минус возвраты, без учёта только `Rejected`).
  - `_check_amount()` — сумма не должна превышать остаток по заказу; иначе `OverpaymentError`.
  - `create_acquiring_payment()` — проверки → вызов `AcquiringClient.start_payment` → создание `PaymentORM` (submitted) → постановка в очередь `check_payment_status_task`.
- **`ReturnPaymentService`** (`return_service.py`) — создание возврата наличными:
  - `_get_order_for_update()`, `_check_order_belongs_to_user()` — аналогично.
  - `_get_completed_balance()` — баланс только по завершённым платежам.
  - `create_return()` — проверка, что сумма возврата ≤ completed_balance; создание платежа return/cash/completed; пересчёт `order.payment_status` через `PaymentStatusChecker._get_order_payment_status`.
- **`PaymentStatusChecker`** (`status_checker.py`) — проверка статуса в эквайринге и обновление БД:
  - `_get_payment_for_update(payment_id)` — платёж не в терминальном состоянии, с `bank_payment_id`, с блокировкой.
  - `_check_payment_info()` — валидация ответа эквайринга через Pydantic `AcquiringPaymentInfo`.
  - `_get_order_payment_status(order)` — расчёт статуса заказа по завершённым платежам (unpaid / partially paid / paid).
  - `check_and_update(payment_id)` — запрос к API эквайринга, обновление статуса платежа и при `completed` — `paid_at` и статус заказа; возвращает `True`, если платёж в терминальном состоянии.

### Исключения (`src.app.services.payment.exceptions`)

- **`OverpaymentError`** — сумма платежа превышает остаток по заказу; атрибут `remaining_amount`.
- **`OrderNotFoundError`** — заказ не найден.
- **`ForbiddenOrderAccessError`** — доступ к заказу запрещён.
- **`ReturnAmountExceedsBalanceError`** — сумма возврата больше доступного баланса; атрибут `available_amount`.
- **`PaymentNotFoundError`**, **`ForbiddenPaymentAccessError`**, **`PaymentNotCancellableError`** — для сценариев с платежами.

---

## Клиенты внешних сервисов

### `src.app.clients.acquiring`

- **`AcquiringStartError`** — ошибка при вызове «старт платежа».
- **`AcquiringCheckError`** — ошибка при проверке статуса.
- **`AcquiringPaymentNotFoundError`** — ответ эквайринга «платёж не найден».
- **`AcquiringClient`**:
  - `start_payment(order_id, amount)` — POST на `ACQUIRING_START_URL`; поддерживает ответ JSON (`payment_id`) или plain text; возвращает `bank_payment_id`; при ошибке — `AcquiringStartError`.
  - `check_payment(bank_payment_id)` — POST на `ACQUIRING_CHECK_URL`; ожидает JSON; при `{"error": "Платеж не найден"}` — `AcquiringPaymentNotFoundError`; при прочих ошибках — `AcquiringCheckError`.

---

## База данных

### `src.app.db.postgres`

- **`PgConnector`** — асинхронный движок и фабрика сессий SQLAlchemy:
  - `connect()` — создание engine и `async_sessionmaker`.
  - `close()` — закрытие engine.
  - `get_session()` — генератор сессий.
  - `async_session_maker` — свойство для получения фабрики сессий.
- **`get_postgres_provider(test)`** — синглтон провайдера (тестовый или боевой URL).
- **`get_async_db_session`** — зависимость FastAPI: одна сессия на запрос, при ошибке — rollback.

### `src.app.db.redis`

- **`RedisClient`** — подключение/отключение к Redis; используется в lifespan приложения и для Celery (broker/backend).
- **`get_redis_provider(test)`** — провайдер Redis.

---

## Модели данных

### `src.app.models.db_models.base`

- **`Base`** — DeclarativeBase SQLAlchemy.
- **`BaseFields`** — абстрактная модель: `id`, `created_at`, `updated_at` (server_default/onupdate).

### `src.app.models.db_models.user`

- **`UserORM`** — таблица `user`: поля FastAPI-Users (email, hashed_password, is_active, is_superuser, is_verified) + `name`, `phone_number`; связи `revoked_tokens`, `orders`, `payments`.
- **`RevokedToken`** — таблица `revoked_tokens`: `token`, `user_id` (FK → user), связь `user`.

### `src.app.models.db_models.order`

- **`OrderPaymentStatus`** — enum: `unpaid`, `paid`, `partially paid`.
- **`OrderORM`** — таблица `order`: `user_id`, `payment_status`, `total_sum`; связи `user`, `payments`.

### `src.app.models.db_models.payment`

- **`PaymentType`** — `cash`, `acquiring`.
- **`OperationType`** — `deposit`, `return`.
- **`PaymentStatus`** — `submitted`, `processing`, `completed`, `rejected`.
- **`PaymentORM`** — таблица `payment`: `user_id`, `order_id`, `payment_status`, `payment_type`, `operation_type`, `amount`, `bank_payment_id`, `paid_at`; связи `user`, `order`.

### Валидаторы (`src.app.models.validators`)

- Pydantic-схемы для API: например `PaymentCreate`, `PaymentRead`, `AcquiringPaymentInfo` (для ответа эквайринга).

---

## Фоновые задачи (Celery)

### `src.app.tasks.tasks`

- **`check_payment_status_task`** — задача с retry: создаёт async-сессию через `postgres_session()`, вызывает `PaymentStatusChecker(session).check_and_update(payment_id)`; при не терминальном статусе или ошибке — повтор через 30–60 сек, до 10 попыток.
- **`enqueue_payment_status_checks_task`** — выбирает id всех платежей не в статусе Completed/Rejected с заполненным `bank_payment_id`, для каждого ставит в очередь `check_payment_status_task`; вызывается по расписанию (crontab каждые 3 часа).

### `src.app.tasks.utils`

- **`postgres_session()`** — контекстный менеджер: создаёт отдельный `PgConnector`, подключается, выдаёт сессию; используется в Celery-задачах (синхронный код запускает async через `asyncio.run`).

---

## Конфигурация

### `src.app.core.config`

- **`Settings`** — Pydantic BaseSettings, загрузка из `.env`: проект, окружение, порт/хост, логи; PostgreSQL, Redis, JWT (secret, algorithm, TTL access/refresh); URL эквайринга; PAGE_SIZE, TEST. Свойства: `POSTGRES_URL`, `POSTGRES_TEST_URL`, `REDIS_URL`, `REDIS_TEST_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `AUTOFLUSH` / `AUTOFLUSH_TEST`.

### `src.app.core.constants`

- **`PAYMENT_BANK_ID`** — ключ `"payment_id"` для тела запросов/ответов API эквайринга.

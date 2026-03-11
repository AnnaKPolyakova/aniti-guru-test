## Описание таблиц

### `user`

Пользователи (FastAPI-Users + доп. поля).

| Колонка           | Тип        | Описание                          |
|-------------------|------------|-----------------------------------|
| id                | int PK     | Первичный ключ                    |
| created_at        | datetime   | Время создания                    |
| updated_at        | datetime   | Время обновления                  |
| email             | string UK  | Email                             |
| hashed_password   | string     | Хеш пароля                        |
| is_active         | bool       | Активен ли пользователь           |
| is_superuser      | bool       | Суперпользователь                 |
| is_verified       | bool       | Верифицирован                     |
| name              | string     | Имя (nullable)                    |
| phone_number      | string(20) | Телефон, уникальный (nullable)    |

**Связи:** один пользователь — много `revoked_tokens`, много `order`, много `payment`.

---

### `revoked_tokens`

Чёрный список JWT (отозванные токены).

| Колонка    | Тип      | Описание        |
|------------|----------|-----------------|
| id         | int PK   | Первичный ключ  |
| created_at | datetime | Время создания  |
| updated_at | datetime | Время обновления|
| token      | string UK| Значение токена |
| user_id    | int FK   | Ссылка на user  |

**Связи:** многие записи — к одному `user`.

---

### `order`

Заказы пользователей.

| Колонка        | Тип           | Описание                                      |
|----------------|---------------|-----------------------------------------------|
| id             | int PK        | Первичный ключ                                |
| created_at     | datetime      | Время создания                                |
| updated_at     | datetime      | Время обновления                              |
| user_id        | int FK        | Владелец заказа                               |
| payment_status | string(20)    | unpaid / partially paid / paid                |
| total_sum      | numeric(10,2) | Сумма заказа                                  |

**Связи:** один `user` — много `order`; один `order` — много `payment`.

---

### `payment`

Платежи по заказам (пополнения и возвраты).

| Колонка         | Тип            | Описание                                      |
|-----------------|----------------|-----------------------------------------------|
| id              | int PK         | Первичный ключ                                |
| created_at      | datetime       | Время создания                                |
| updated_at      | datetime       | Время обновления                              |
| user_id         | int FK         | Пользователь                                  |
| order_id        | int FK         | Заказ                                         |
| payment_status  | string(20)     | submitted / processing / completed / rejected |
| payment_type    | string(20)     | cash / acquiring                              |
| operation_type  | string(20)     | deposit / return                              |
| amount          | numeric(10,2)   | Сумма                                         |
| bank_payment_id | string(255)    | ID платежа в эквайринге (nullable)            |
| paid_at         | datetime TZ    | Время фактической оплаты (nullable)           |

**Связи:** многие `payment` — к одному `user` и к одному `order`.

---

## Перечисления (значения в БД)

- **order.payment_status:** `unpaid`, `partially paid`, `paid`
- **payment.payment_status:** `submitted`, `processing`, `completed`, `rejected`
- **payment.payment_type:** `cash`, `acquiring`
- **payment.operation_type:** `deposit`, `return`

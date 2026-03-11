# Схема БД: блоки и связи

Отдельный файл с диаграммой в формате «блоки и стрелки».
```
    ┌─────────────────────────────────┐
    │ USER                             │
    │ id                 int PK        │
    │ created_at         datetime      │
    │ updated_at         datetime      │
    │ email              string UK     │
    │ hashed_password    string        │
    │ is_active          bool          │
    │ is_superuser       bool          │
    │ is_verified        bool          │
    │ name               string        │
    │ phone_number       string UK     │
    └────────────────┬────────────────┘
       │
       ├── 1:M ──▶ ┌─────────────────────────────────┐
       │           │ REVOKED_TOKENS                   │
       │           │ id           int PK              │
       │           │ created_at   datetime            │
       │           │ updated_at   datetime            │
       │           │ token        string UK           │
       │           │ user_id      int FK              │
       │           └─────────────────────────────────┘
       │
       ├── 1:M ──▶ ┌─────────────────────────────────┐
       │           │ ORDER                            │
       │           │ id              int PK          │
       │           │ created_at      datetime         │
       │           │ updated_at      datetime        │
       │           │ user_id         int FK          │
       │           │ payment_status  string          │
       │           │ total_sum       numeric         │
       │           └────────────────┬────────────────┘
       │                             │ 1:M
       │                             ▼
       │           ┌─────────────────────────────────┐
       └── 1:M ──▶ │ PAYMENT                          │
                   │ id              int PK          │
                   │ created_at      datetime        │
                   │ updated_at      datetime        │
                   │ user_id         int FK          │
                   │ order_id        int FK          │
                   │ payment_status  string          │
                   │ payment_type    string          │
                   │ operation_type  string          │
                   │ amount          numeric         │
                   │ bank_payment_id string          │
                   │ paid_at         datetime        │
                   └─────────────────────────────────┘
```

# GetCourse REST API — База знаний

## Документация
- Справка API: https://getcourse.ru/help/api
- Блог об API: https://getcourse.ru/blog/276212

## Особенности API
⚠️ GetCourse использует нестандартный подход:
- Параметры запроса передаются как JSON → кодируется в base64 → отправляется в POST
- Export (получение данных) — двухшаговый: запрос + polling
- Import (запись данных) — одношаговый

## Аутентификация
Используется `secret_key` аккаунта GetCourse.
Получить: Аккаунт → Настройки → Интеграция → Ключ API (secret_key)

## Базовый URL
```
https://ACCOUNT_NAME.getcourse.ru/pl/api/
```

## Формат запроса
```python
import json, base64, requests

ACCOUNT = "your_account_name"
SECRET_KEY = "your_secret_key"
BASE_URL = f"https://{ACCOUNT}.getcourse.ru/pl/api"

def make_params(data: dict) -> str:
    """Сериализуем параметры: dict -> JSON -> base64"""
    return base64.b64encode(json.dumps(data).encode()).decode()
```

## EXPORT — Получение данных (двухшаговый)

### Шаг 1: Отправить запрос на экспорт
```
POST https://ACCOUNT.getcourse.ru/pl/api/account/users
params=BASE64_JSON&key=SECRET_KEY&async=1
```

Параметры запроса (до base64):
```json
{
  "action": "export",
  "params": {
    "rules": {
      "field": "email",
      "condition": "contains",
      "value": "@gmail.com"
    },
    "selected_ids": [1, 2, 3],
    "offset": 0,
    "count": 10,
    "orders": [
      {"field": "id", "order": "asc"}
    ],
    "exports": ["id", "email", "firstname", "lastname", "phone"]
  }
}
```

Ответ шага 1:
```json
{
  "success": true,
  "info": {
    "export_id": 12345
  }
}
```

### Шаг 2: Polling — запрос результата
```
GET https://ACCOUNT.getcourse.ru/pl/api/account/exports/12345?key=SECRET_KEY
```

Ответ (пока не готово):
```json
{"success": true, "info": {"state": "processing"}}
```

Ответ (готово):
```json
{
  "success": true,
  "info": {
    "state": "completed",
    "items": [
      {"id": 1, "email": "user@gmail.com", "firstname": "Иван"}
    ],
    "total": 100
  }
}
```

## IMPORT — Запись данных (одношаговый)

### Добавление/обновление пользователя
```
POST https://ACCOUNT.getcourse.ru/pl/api/account/users
params=BASE64_JSON&key=SECRET_KEY
```

Параметры (до base64):
```json
{
  "action": "import",
  "params": {
    "users": [
      {
        "email": "user@example.com",
        "phone": "+79001234567",
        "firstname": "Иван",
        "lastname": "Иванов",
        "addfields": {
          "custom_field": "value"
        },
        "group": {
          "add": ["Группа 1", "VIP"],
          "remove": ["Старая группа"]
        }
      }
    ],
    "return_user_id": "Y"
  }
}
```

### Добавление заказа пользователю
```json
{
  "action": "import",
  "params": {
    "users": [
      {
        "email": "user@example.com",
        "deals": [
          {
            "deal_number": "UNIQUE_DEAL_ID",
            "offer_code": "OFFER_CODE",
            "deal_cost": 5000,
            "deal_currency": "rub",
            "deal_status": "paid",
            "manager_email": "manager@company.ru",
            "utm_source": "instagram",
            "utm_medium": "cpc"
          }
        ]
      }
    ]
  }
}
```

## Ключевые объекты API

### Пользователи
- Endpoint: `/pl/api/account/users`
- Поля: id, email, phone, firstname, lastname, addfields (доп. поля), registered_at

### Заказы (deals)
- Endpoint: `/pl/api/account/deals`
- Поля: id, deal_number, user_email, offer_code, deal_cost, deal_status, created_at

### Группы
- Endpoint: `/pl/api/account/groups`
- Операции: список групп

### Курсы
- Endpoint: `/pl/api/account/courses`

### Офферы (продукты)
- Endpoint: `/pl/api/account/offers`

## Статусы заказов
| Код | Описание |
|-----|----------|
| `new` | Новый |
| `paid` | Оплачен |
| `cancelled` | Отменён |
| `pending` | Ожидает оплаты |
| `partial_paid` | Частично оплачен |

## Полный пример кода Python
```python
import json, base64, requests, time

ACCOUNT = "your_account"
SECRET_KEY = "your_secret_key"
BASE_URL = f"https://{ACCOUNT}.getcourse.ru/pl/api"

def gc_export(endpoint, params):
    """Двухшаговый экспорт с polling"""
    payload = {"action": "export", "params": params}
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    
    # Шаг 1: запросить экспорт
    r = requests.post(f"{BASE_URL}/{endpoint}", data={
        "params": encoded,
        "key": SECRET_KEY,
        "async": 1
    })
    export_id = r.json()["info"]["export_id"]
    
    # Шаг 2: polling
    while True:
        r = requests.get(f"{BASE_URL}/account/exports/{export_id}", 
                         params={"key": SECRET_KEY})
        data = r.json()["info"]
        if data["state"] == "completed":
            return data["items"]
        time.sleep(2)

def gc_import(endpoint, users_data):
    """Одношаговый импорт"""
    payload = {"action": "import", "params": {"users": users_data}}
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    r = requests.post(f"{BASE_URL}/{endpoint}", data={
        "params": encoded,
        "key": SECRET_KEY
    })
    return r.json()

# Получить всех пользователей с email @gmail.com
users = gc_export("account/users", {
    "exports": ["id", "email", "firstname", "phone"]
})

# Добавить пользователя
gc_import("account/users", [{
    "email": "new@example.com",
    "firstname": "Новый",
    "group": {"add": ["Покупатели"]}
}])
```

## Ограничения
- Максимум 500 пользователей в одном импорт-запросе
- Polling: рекомендуется пауза 2-5 сек между проверками
- Тарифы: API доступен только на платных тарифах

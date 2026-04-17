# Avito API — Быстрый вход

## Что работает

### Токен (client_credentials)
```python
import requests

CLIENT_ID = "NO3toc3esodDkZeF8Qjq"       # персональное приложение
CLIENT_SECRET = "P9D0bPn-sO3HAXVoGHKdiskzqrePrDkPwzxqubXn"

token = requests.post("https://api.avito.ru/token", data={
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET
}).json()["access_token"]

headers = {"Authorization": f"Bearer {token}"}
USER_ID = 399993528  # "Настройка Битрикс24"
```

### Рабочие endpoint'ы
```python
# Все активные объявления (пагинация по 100)
requests.get("https://api.avito.ru/core/v1/items", headers=headers,
             params={"per_page": 100, "page": 1, "status": "active"})
# Итого: 1002 активных объявления

# Профиль
requests.get("https://api.avito.ru/core/v1/accounts/self", headers=headers)
```

### Что НЕ работает
- `/core/v1/accounts/{user_id}/items` → 404
- `/stats/v1/accounts/{user_id}/items` → временно недоступен (на стороне Avito)
- Позиции в выдаче через API — не существует, только парсинг или сторонние сервисы

## Приложения аккаунта 399993528
| Приложение | Client ID | Доступы |
|------------|-----------|---------|
| Персональная авторизация | NO3toc3esodDkZeF8Qjq | базовые |
| extravert-1-automation | TUpTQjTDwZru3SaJVGBl | items:info, messenger, stats:read, user:read |
| reporttest | i2pDYYCFav84tS1Texz0 | — |

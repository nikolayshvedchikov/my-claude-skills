# Avito REST API — База знаний

## Документация
- Портал разработчика: https://developers.avito.ru
- Профессиональный API: https://www.avito.ru/professionals/api
- Правила публичного API: https://www.avito.ru/legal/pro_tools/public-api

## Доступ к API
- Необходимо подать заявку на доступ через портал developers.avito.ru
- Для базовых функций (объявления, статистика) — стандартная заявка
- Для мессенджера и расширенных функций — отдельное согласование

## Аутентификация — OAuth 2.0

### Получение токена (client_credentials)
```
POST https://api.avito.ru/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&
client_id=CLIENT_ID&
client_secret=CLIENT_SECRET
```
Ответ:
```json
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 86400
}
```

### Использование токена
```
Authorization: Bearer ACCESS_TOKEN
```

## Базовый URL
```
https://api.avito.ru/
```

## Ключевые разделы API

### Объявления (Items)
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/core/v1/accounts/{user_id}/items` | GET | Список объявлений |
| `/core/v1/accounts/{user_id}/items/{item_id}` | GET | Получить объявление |
| `/core/v1/accounts/{user_id}/items/{item_id}/stats` | GET | Статистика объявления |
| `/core/v1/items` | POST | Создать объявление |
| `/core/v1/accounts/{user_id}/items/{item_id}` | PUT | Обновить объявление |

### Параметры объявлений
- `status`: active, blocked, removed, old, inactive
- `category_id`: ID категории
- `location_id`: ID города

### Мессенджер (Messenger)
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/messenger/v3/accounts/{user_id}/chats` | GET | Список чатов |
| `/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages` | GET | Сообщения чата |
| `/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages` | POST | Отправить сообщение |

### Статистика
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/stats/v1/accounts/{user_id}/items` | POST | Статистика по объявлениям |
| `/core/v1/accounts/{user_id}/calls/stats` | GET | Статистика звонков |

### Кошелёк
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/core/v1/accounts/{user_id}/balance/` | GET | Баланс счёта |

### Автозагрузка
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/autoload/v2/accounts/{user_id}/reports` | GET | Отчёты автозагрузки |

## Получение user_id
```
GET https://api.avito.ru/core/v1/accounts/self
Authorization: Bearer ACCESS_TOKEN
```

## Формат ответа
```json
{
  "items": [...],
  "meta": {
    "total": 100,
    "page": 1,
    "per_page": 25
  }
}
```

## Лимиты
- 10 запросов/сек на аккаунт
- 1000 запросов/час для статистики

## Вебхуки (уведомления)
- Поддерживаются для событий мессенджера
- Настройка в личном кабинете разработчика
- События: новое сообщение, изменение статуса объявления

## Пример кода Python
```python
import requests

CLIENT_ID = "your_client_id"
CLIENT_SECRET = "your_client_secret"

# Получить токен
def get_token():
    r = requests.post("https://api.avito.ru/token", data={
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    })
    return r.json()["access_token"]

TOKEN = get_token()
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Получить свой user_id
me = requests.get("https://api.avito.ru/core/v1/accounts/self", headers=HEADERS).json()
user_id = me["id"]

# Список объявлений
items = requests.get(
    f"https://api.avito.ru/core/v1/accounts/{user_id}/items",
    headers=HEADERS,
    params={"status": "active", "per_page": 25}
).json()
```

## Категории
Категории Avito имеют числовые ID. Получить дерево категорий:
```
GET https://api.avito.ru/core/v1/items/categories
```

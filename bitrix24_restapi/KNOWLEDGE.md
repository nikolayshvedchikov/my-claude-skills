# Bitrix24 REST API — База знаний

## Документация
- Основная: https://apidocs.bitrix24.com
- Быстрый старт: https://apidocs.bitrix24.com/first-steps/access-to-rest-api.html

## Аутентификация

### Вариант 1: OAuth 2.0 (для приложений)
```
GET https://YOUR_DOMAIN.bitrix24.ru/oauth/authorize/?
  client_id=CLIENT_ID&
  response_type=code&
  redirect_uri=REDIRECT_URI

POST https://oauth.bitrix.info/oauth/token/
  grant_type=authorization_code&
  client_id=CLIENT_ID&
  client_secret=CLIENT_SECRET&
  code=CODE&
  redirect_uri=REDIRECT_URI
```
Ответ: `{ "access_token": "...", "refresh_token": "...", "expires_in": 3600 }`

Обновление токена:
```
POST https://oauth.bitrix.info/oauth/token/
  grant_type=refresh_token&
  client_id=CLIENT_ID&
  client_secret=CLIENT_SECRET&
  refresh_token=REFRESH_TOKEN
```

### Вариант 2: Входящий вебхук (для личного использования)
```
https://YOUR_DOMAIN.bitrix24.ru/rest/USER_ID/WEBHOOK_TOKEN/METHOD
```

## Базовый URL и формат запросов
```
https://YOUR_DOMAIN.bitrix24.ru/rest/METHOD
```
Параметры передаются как:
- GET: строка запроса
- POST: form-data или JSON с заголовком `Content-Type: application/json`

Авторизация через токен: добавить параметр `auth=ACCESS_TOKEN` или заголовок `Authorization: Bearer ACCESS_TOKEN`

## Формат ответа
```json
{
  "result": { ... },      // или массив
  "next": 50,             // для пагинации (если есть ещё записи)
  "total": 150            // всего записей
}
```
Ошибка:
```json
{
  "error": "ERROR_CODE",
  "error_description": "Human readable message"
}
```

## Пагинация
- По умолчанию: 50 записей
- Параметр `start=N` — смещение
- Если в ответе есть `next`, значит есть ещё записи

## Лимиты
- 2 запроса/сек на пользователя
- Массовые операции: batch до 50 методов за раз

## Batch-запросы (до 50 методов)
```json
POST /rest/batch
{
  "halt": 0,
  "cmd": {
    "get_user": "user.current",
    "get_deals": "crm.deal.list?filter[STAGE_ID]=NEW&select[]=ID&select[]=TITLE"
  }
}
```

## Ключевые методы

### CRM — Лиды
| Метод | Описание |
|-------|----------|
| `crm.lead.list` | Список лидов |
| `crm.lead.get` | Получить лид по ID |
| `crm.lead.add` | Создать лид |
| `crm.lead.update` | Обновить лид |
| `crm.lead.delete` | Удалить лид |
| `crm.lead.fields` | Список полей |

### CRM — Сделки
| Метод | Описание |
|-------|----------|
| `crm.deal.list` | Список сделок |
| `crm.deal.get` | Получить сделку |
| `crm.deal.add` | Создать сделку |
| `crm.deal.update` | Обновить сделку |
| `crm.deal.delete` | Удалить сделку |
| `crm.deal.fields` | Список полей |
| `crm.dealcategory.list` | Воронки/категории |
| `crm.deal.productrows.get` | Товары в сделке |
| `crm.deal.productrows.set` | Установить товары |

### CRM — Контакты
| Метод | Описание |
|-------|----------|
| `crm.contact.list` | Список контактов |
| `crm.contact.get` | Получить контакт |
| `crm.contact.add` | Создать |
| `crm.contact.update` | Обновить |

### CRM — Компании
| Метод | Описание |
|-------|----------|
| `crm.company.list` | Список компаний |
| `crm.company.get` | Получить |
| `crm.company.add` | Создать |
| `crm.company.update` | Обновить |

### CRM — Активности (звонки, письма, встречи)
| Метод | Описание |
|-------|----------|
| `crm.activity.list` | Список активностей |
| `crm.activity.add` | Создать активность |
| `crm.activity.update` | Обновить |
| `crm.activity.delete` | Удалить |

### CRM — Стадии воронки
```
crm.dealcategory.list — список воронок
crm.dealcategorystage.list?id=CATEGORY_ID — стадии воронки
```

### Задачи
| Метод | Описание |
|-------|----------|
| `tasks.task.list` | Список задач |
| `tasks.task.get` | Получить задачу |
| `tasks.task.add` | Создать задачу |
| `tasks.task.update` | Обновить |
| `tasks.task.delete` | Удалить |
| `tasks.task.complete` | Завершить |
| `tasks.comment.add` | Добавить комментарий |

### Пользователи
| Метод | Описание |
|-------|----------|
| `user.current` | Текущий пользователь |
| `user.get` | Получить пользователей |
| `user.search` | Поиск |
| `department.get` | Отделы |

### Каталог / Товары
| Метод | Описание |
|-------|----------|
| `catalog.product.list` | Список товаров |
| `catalog.product.get` | Получить товар |
| `catalog.product.add` | Создать |
| `crm.product.list` | Товары CRM (старый API) |

### Диски / Файлы
| Метод | Описание |
|-------|----------|
| `disk.folder.getchildren` | Содержимое папки |
| `disk.file.get` | Получить файл |
| `disk.file.uploadurl.get` | URL для загрузки |

### Вебхуки (исходящие)
| Метод | Описание |
|-------|----------|
| `event.bind` | Подписаться на событие |
| `event.unbind` | Отписаться |
| `event.get` | Список подписок |

Ключевые события: `ONCRMLEADADD`, `ONCRMDEALUPDATE`, `ONCRMCONTACTADD`, `ONTASKUPDATE`

## Фильтры и выборки
```json
crm.deal.list?
  filter[STAGE_ID]=WON&
  filter[>DATE_CREATE]=2024-01-01&
  select[]=ID&
  select[]=TITLE&
  select[]=OPPORTUNITY&
  order[DATE_CREATE]=DESC&
  start=0
```

## Пользовательские поля
- Имена начинаются с `UF_CRM_` (для CRM) или `UF_` (для других сущностей)
- Для получения: `crm.userfield.list?ENTITY_ID=CRM_DEAL`

## Типичные ошибки
| Код | Причина |
|-----|---------|
| `WRONG_AUTH_TYPE` | Неверная авторизация |
| `NO_AUTH_FOUND` | Токен не передан |
| `expired_token` | Токен истёк — нужен refresh |
| `QUERY_LIMIT_EXCEEDED` | Превышен лимит запросов |
| `ACCESS_DENIED` | Нет прав |

## Примеры кода Python

```python
import requests

DOMAIN = "your_domain.bitrix24.ru"
TOKEN = "your_access_token"
BASE_URL = f"https://{DOMAIN}/rest"

def call(method, params=None):
    url = f"{BASE_URL}/{method}"
    params = params or {}
    params["auth"] = TOKEN
    r = requests.post(url, json=params)
    return r.json()

# Получить список сделок
deals = call("crm.deal.list", {
    "filter": {"STAGE_ID": "NEW"},
    "select": ["ID", "TITLE", "OPPORTUNITY"],
    "order": {"DATE_CREATE": "DESC"}
})

# Создать лид
lead = call("crm.lead.add", {
    "fields": {
        "TITLE": "Новый лид",
        "NAME": "Иван",
        "LAST_NAME": "Иванов",
        "PHONE": [{"VALUE": "+79001234567", "VALUE_TYPE": "WORK"}],
        "EMAIL": [{"VALUE": "ivan@example.com", "VALUE_TYPE": "WORK"}],
        "SOURCE_ID": "CALL"
    }
})
```

# 1С:Фреш REST API — База знаний

## Документация
- Главная: https://its.1c.ru/db/fresh
- REST API портала ИТС: https://its.1c.ru/db/fresh/content/37655176/hdoc
- OData-интерфейс: https://1cfresh.com/articles/data_odata
- Библиотека интеграции v1.0.6: https://its.1c.ru/db/content/freshsd/src/48727915.html
- Доступ к API приложений: https://its.1c.ru/db/freshpub/content/4227/hdoc

## Архитектура 1С:Фреш

### Компоненты
- **Менеджер сервиса** — управление абонентами, приложениями, пользователями
- **Информационные базы (ИБ)** — данные абонентов (1С:Бухгалтерия, ЗУП и т.д.)
- **Портал 1С:ИТС** — интеграция через REST API

### Два уровня API
1. **API портала (управляющий)** — управление инстансами Фреш, абонентами
2. **API приложений (данные)** — OData для чтения/записи данных ИБ

## Аутентификация

### OpenID Connect + токены доступа
1. Зарегистрировать стороннее приложение в менеджере сервиса:
   - Настройки → Аутентификация → Параметры провайдера аутентификации
   - Задать Client ID и Client Secret
   - Создать ключи подписи токенов

2. Получить токен (OAuth 2.0 Authorization Code Flow):
```
GET https://FRESH_HOST/e1cib/oidc/authentication?
  response_type=code&
  client_id=CLIENT_ID&
  redirect_uri=REDIRECT_URI&
  scope=openid
```

3. Обменять код на токен:
```
POST https://FRESH_HOST/e1cib/oidc/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code=CODE&
client_id=CLIENT_ID&
client_secret=CLIENT_SECRET&
redirect_uri=REDIRECT_URI
```

## OData API — Доступ к данным ИБ

### Базовый URL
```
https://FRESH_HOST/ZONE/ib/APP_ID/odata/standard.odata/
```

### Включение OData в приложении
Администрирование → Интернет-поддержка и сервисы → Интеграция с другими программами → Разрешить доступ внешним приложениям ✓

### Формат запросов (OData v3)
```
GET /odata/standard.odata/Catalog_Контрагенты?
  $format=json&
  $top=10&
  $filter=ИНН eq '7700000000'&
  $select=Ref_Key,Description,ИНН,КПП

Authorization: Bearer ACCESS_TOKEN
```

### Основные операции

#### Получение списка (GET)
```
GET /odata/standard.odata/ENTITY_NAME
  ?$format=json
  &$top=100
  &$skip=0
  &$filter=FIELD eq 'VALUE'
  &$select=FIELD1,FIELD2
  &$orderby=FIELD asc
```

#### Получение одного объекта (GET)
```
GET /odata/standard.odata/ENTITY_NAME(guid'GUID')
  ?$format=json
```

#### Создание объекта (POST)
```
POST /odata/standard.odata/ENTITY_NAME
Content-Type: application/json
{
  "Description": "Название",
  "ИНН": "7700000000"
}
```
⚠️ Запись через OData ограничена! Основной механизм для записи — HTTP-сервисы 1С

#### Вызов метода (действие)
```
POST /odata/standard.odata/Document_РеализацияТоваровУслуг_Провести
  ?Document_key=guid'GUID'
```

### Ключевые сущности (типичные конфигурации)

#### 1С:Бухгалтерия
| Имя OData | Описание |
|-----------|----------|
| `Catalog_Контрагенты` | Контрагенты |
| `Catalog_Номенклатура` | Номенклатура |
| `Catalog_Банки` | Банки |
| `Document_РеализацияТоваровУслуг` | Реализация |
| `Document_СчетНаОплатуПокупателю` | Счёт на оплату |
| `Document_ПоступлениеТоваровУслуг` | Поступление |
| `InformationRegister_КурсыВалют` | Курсы валют |

#### Поля контрагента
```json
{
  "Ref_Key": "guid'...'",
  "Description": "ООО Ромашка",
  "ИНН": "7700000000",
  "КПП": "770001001",
  "ЮрФизЛицо": "ЮрЛицо",
  "НаименованиеПолное": "Общество с ограниченной ответственностью Ромашка"
}
```

### Фильтры OData
```
$filter=ИНН eq '7700000000'
$filter=DeletionMark eq false
$filter=Date gt datetime'2024-01-01T00:00:00'
$filter=contains(Description,'Ромашка')
```

## REST API портала 1С:ИТС

### Управление абонентами
```
GET https://api.1cfresh.com/api/v1/abonents
Authorization: Bearer PORTAL_TOKEN

GET https://api.1cfresh.com/api/v1/abonents/{abonent_id}/applications
```

### Управление пользователями
```
GET https://api.1cfresh.com/api/v1/abonents/{id}/users
POST https://api.1cfresh.com/api/v1/abonents/{id}/users
```

## Пример кода Python
```python
import requests

FRESH_HOST = "https://1cfresh.com"
ACCESS_TOKEN = "your_token"
APP_ID = "your_app_id"
ODATA_BASE = f"{FRESH_HOST}/zone/ib/{APP_ID}/odata/standard.odata"

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Accept": "application/json"
}

# Получить список контрагентов
def get_contractors(inn=None):
    params = {"$format": "json", "$top": 100}
    if inn:
        params["$filter"] = f"ИНН eq '{inn}'"
    r = requests.get(f"{ODATA_BASE}/Catalog_Контрагенты", headers=HEADERS, params=params)
    return r.json()["value"]

# Получить документы реализации за период
def get_sales(date_from, date_to):
    params = {
        "$format": "json",
        "$filter": f"Date gt datetime'{date_from}T00:00:00' and Date lt datetime'{date_to}T23:59:59'",
        "$select": "Ref_Key,Number,Date,Контрагент_Key,СуммаДокумента"
    }
    r = requests.get(f"{ODATA_BASE}/Document_РеализацияТоваровУслуг", headers=HEADERS, params=params)
    return r.json()["value"]
```

## Настройка прав доступа (пошагово)
1. Менеджер сервиса → Настройки → Аутентификация → Свойства сторонних приложений
2. Создать Client ID + Client Secret
3. Создать ключи подписи токенов
4. В публикации ИБ (default.vrd) прописать OpenID параметры
5. В приложении: Администрирование → Интеграция → Разрешить доступ
6. Назначить пользователю дополнительные роли в менеджере сервиса

## Ограничения OData в Фреш
- Только режим чтения для большинства операций
- Для записи использовать HTTP-сервисы конфигурации
- Объём выборки ограничен (рекомендуется $top не более 1000)

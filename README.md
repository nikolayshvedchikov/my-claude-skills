# Claude Skills — API Knowledge Base

Репозиторий с базами знаний по REST API сервисов для работы Claude.

## Как использовать
Перед решением задачи Claude читает `KNOWLEDGE.md` нужного подпроекта и работает без паузы на изучение.

## Подпроекты

| Проект | Сервис | Аутентификация | Документация |
|--------|--------|---------------|-------------|
| [bitrix24_restapi](./bitrix24_restapi/) | Bitrix24 REST API | OAuth 2.0 / Webhook | [apidocs.bitrix24.com](https://apidocs.bitrix24.com) |
| [bitrix24_vibecode](./bitrix24_vibecode/) | Bitrix24 Vibecode (MCP) | Webhook | [vibecode.bitrix24.tech/docs](https://vibecode.bitrix24.tech/docs) |
| [avito_restapi](./avito_restapi/) | Avito REST API | OAuth 2.0 | [developers.avito.ru](https://developers.avito.ru) |
| [hh_restapi](./hh_restapi/) | HeadHunter REST API | OAuth 2.0 | [github.com/hhru/api](https://github.com/hhru/api) |
| [1C_restapi](./1C_restapi/) | 1С:Фреш REST/OData | OpenID + токен | [its.1c.ru/db/fresh](https://its.1c.ru/db/fresh) |
| [getcourse_restapi](./getcourse_restapi/) | GetCourse API | Secret Key | [getcourse.ru/help/api](https://getcourse.ru/help/api) |

## Сводная таблица API

| Сервис | Тип | Формат | Особенности |
|--------|-----|--------|-------------|
| Bitrix24 | REST | JSON | 2 req/s, batch до 50 методов |
| Avito | REST | JSON | Нужна заявка на доступ |
| HeadHunter | REST | JSON | Обязателен HH-User-Agent |
| 1С:Фреш | OData v3 / REST | JSON/XML | OData только чтение |
| GetCourse | REST Import/Export | JSON→base64 | Export двухшаговый (polling) |

## Структура каждого подпроекта
```
SERVICE_NAME/
├── README.md      — краткое описание
└── KNOWLEDGE.md   — полная база знаний: auth, endpoints, примеры кода
```

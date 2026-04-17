# Avito — Аккаунты и приложения

⚠️ ВНИМАНИЕ: Реальные секреты НЕ хранить в публичном репо. Ниже — структура для учёта. Сами значения — в защищённом хранилище.

---

## Аккаунт: Настройка Битрикс24
- Номер профиля: 399 993 528

### Приложения

| Название | Client ID | Redirect URL | Доступы |
|----------|-----------|-------------|---------|
| Персональная авторизация | NO3toc3esodDkZeF8Qjq | — | базовые |
| extravert-1-automation | TUpTQjTDwZru3SaJVGBl | https://extravert.bz | items:info, messenger:read/write, stats:read, user:read |
| reporttest | i2pDYYCFav84tS1Texz0 | https://shvedchikov.pro | — |

### Секреты (хранить отдельно, не в git)
```
# .env файл (не коммитить!)
AVITO_CLIENT_ID_PERSONAL=NO3toc3esodDkZeF8Qjq
AVITO_CLIENT_SECRET_PERSONAL=***

AVITO_CLIENT_ID_AUTOMATION=TUpTQjTDwZru3SaJVGBl
AVITO_CLIENT_SECRET_AUTOMATION=***

AVITO_CLIENT_ID_REPORT=i2pDYYCFav84tS1Texz0
AVITO_CLIENT_SECRET_REPORT=***
```

---

## Добавить новый аккаунт (шаблон)
```
## Аккаунт: НАЗВАНИЕ
- Номер профиля: XXXXXXXX

### Приложения
| Название | Client ID | Redirect URL | Доступы |
```

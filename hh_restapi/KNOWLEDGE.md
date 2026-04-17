# HeadHunter (hh.ru) REST API — База знаний

## Документация
- GitHub: https://github.com/hhru/api
- Swagger/OpenAPI: https://api.hh.ru/openapi/redoc
- Портал разработчика: https://dev.hh.ru/admin

## Аутентификация — OAuth 2.0

### Регистрация приложения
1. Зайти на https://dev.hh.ru/admin
2. Создать приложение, получить client_id и client_secret
3. Указать redirect_uri

### Получение кода авторизации
```
GET https://hh.ru/oauth/authorize?
  response_type=code&
  client_id=CLIENT_ID&
  redirect_uri=REDIRECT_URI&
  state=RANDOM_STRING
```

### Обмен кода на токен
```
POST https://hh.ru/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
client_id=CLIENT_ID&
client_secret=CLIENT_SECRET&
code=CODE&
redirect_uri=REDIRECT_URI
```
Ответ:
```json
{
  "access_token": "...",
  "token_type": "bearer",
  "expires_in": 1209600,
  "refresh_token": "..."
}
```

### Токен только для работодателя (client_credentials)
```
POST https://hh.ru/oauth/token
grant_type=client_credentials&
client_id=CLIENT_ID&
client_secret=CLIENT_SECRET
```

### Обновление токена
```
POST https://hh.ru/oauth/token
grant_type=refresh_token&
refresh_token=REFRESH_TOKEN
```

### Использование токена
```
Authorization: Bearer ACCESS_TOKEN
HH-User-Agent: MyApp/1.0 (myapp@example.com)  # ОБЯЗАТЕЛЬНО
```

## Базовый URL
```
https://api.hh.ru/
```

## Заголовки (обязательные)
```
Authorization: Bearer ACCESS_TOKEN
HH-User-Agent: AppName/Version (contact@email.com)
```
⚠️ Без `HH-User-Agent` запросы будут отклонены!

## Ключевые endpoint'ы

### Вакансии
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/vacancies` | GET | Поиск вакансий |
| `/vacancies/{id}` | GET | Получить вакансию |
| `/vacancies` | POST | Создать вакансию (работодатель) |
| `/vacancies/{id}` | PUT | Обновить вакансию |
| `/vacancies/{id}` | DELETE | Архивировать |
| `/employers/{id}/vacancies/active` | GET | Активные вакансии работодателя |
| `/employers/{id}/vacancies/archived` | GET | Архивные вакансии |

Параметры поиска вакансий:
- `text` — поисковый запрос
- `area` — регион (1 = Москва, 2 = Санкт-Петербург)
- `specialization` — специализация
- `salary` — зарплата от
- `currency` — валюта (RUR, USD, EUR)
- `experience` — опыт: noExperience, between1And3, between3And6, moreThan6
- `employment` — занятость: full, part, project, volunteer, probation
- `schedule` — график: fullDay, shift, flexible, remote, flyInFlyOut
- `per_page` — записей на страницу (макс. 100)
- `page` — номер страницы

### Резюме (соискатель)
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/resumes/mine` | GET | Мои резюме |
| `/resumes/{id}` | GET | Получить резюме |
| `/resumes` | POST | Создать резюме |
| `/resumes/{id}` | PUT | Обновить резюме |

### Отклики и приглашения
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/negotiations` | GET | Список откликов (соискатель) |
| `/negotiations` | POST | Откликнуться на вакансию |
| `/negotiations/{id}` | GET | Получить отклик |
| `/employers/{id}/negotiations` | GET | Отклики на вакансии работодателя |
| `/negotiations/{id}/messages` | GET | Сообщения в отклике |
| `/negotiations/{id}/messages` | POST | Отправить сообщение |

### Работодатели
| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/employers` | GET | Поиск работодателей |
| `/employers/{id}` | GET | Профиль работодателя |
| `/employers/{id}/managers` | GET | Менеджеры (для работодателя) |

### Текущий пользователь
```
GET /me — информация о текущем пользователе
GET /accounts — список аккаунтов
```

### Справочники
| Endpoint | Описание |
|----------|----------|
| `/areas` | Регионы |
| `/specializations` | Специализации |
| `/industries` | Отрасли |
| `/currencies` | Валюты |
| `/experience` | Опыт работы |
| `/employment` | Тип занятости |
| `/schedule` | График работы |
| `/vacancy_relations` | Отношения к вакансии |

## Формат ответа
```json
{
  "items": [...],
  "found": 1000,
  "pages": 20,
  "page": 0,
  "per_page": 50
}
```

## Лимиты
- 7 запросов/сек для приложений
- Анонимно: 5 запросов/мин

## Роли (типы токенов)
- **applicant** — соискатель: поиск вакансий, отклики, резюме
- **employer** — работодатель: вакансии, отклики, приглашения
- **anonymous** — только публичные данные

## Скоупы OAuth
- `basic` — базовый доступ
- `resumes` — резюме соискателя
- `negotiations` — отклики соискателя
- `employer_applications` — отклики работодателя
- `vacancies` — управление вакансиями

## Пример кода Python
```python
import requests

ACCESS_TOKEN = "your_access_token"
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "HH-User-Agent": "MyIntegration/1.0 (contact@mycompany.ru)"
}
BASE_URL = "https://api.hh.ru"

# Поиск вакансий Python-разработчика в Москве
vacancies = requests.get(f"{BASE_URL}/vacancies", headers=HEADERS, params={
    "text": "Python разработчик",
    "area": 1,
    "experience": "between1And3",
    "per_page": 20
}).json()

# Получить информацию о текущем пользователе
me = requests.get(f"{BASE_URL}/me", headers=HEADERS).json()

# Откликнуться на вакансию (от имени соискателя)
response = requests.post(f"{BASE_URL}/negotiations", headers=HEADERS, json={
    "vacancy_id": "12345678",
    "resume_id": "my_resume_id",
    "message": "Добрый день! Хочу откликнуться на вашу вакансию."
})
```

## Webhooks (для работодателей)
- Настройка через dev.hh.ru
- События: новый отклик, ответ на приглашение, изменение статуса

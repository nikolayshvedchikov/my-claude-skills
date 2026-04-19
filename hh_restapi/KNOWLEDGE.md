# KNOWLEDGE.md — HH.RU AI-HR Ассистент
## Полный журнал реализации для следующей сессии

> **Цель документа:** Прочитав этот файл, следующая сессия Claude может продолжить или воспроизвести проект без единой ошибки из тех, что были уже совершены.

---

## 1. Что построено

**AI-HR ассистент** на базе n8n + Claude Haiku + HH.RU API + Telegram + Bitrix24.

**Что делает система:**
1. Каждые 5 минут опрашивает HH.RU на новые отклики по всем активным вакансиям работодателя
2. При новом отклике — получает полные данные резюме, отправляет Claude для оценки (score 1-10)
3. Score < 4: отправляет вежливый отказ кандидату, меняет статус в HH.RU на `discard`
4. Score ≥ 4: сохраняет контекст, отправляет кандидату первый квалификационный вопрос
5. При ответе кандидата — задаёт следующий вопрос (всего 3), затем делает итоговую оценку
6. Итог: обновляет сделку в Bitrix24, уведомляет заказчика в Telegram
7. Параллельно: диалог через Telegram для создания вакансий (A/B ветки), ночной отчёт (E-ветка)

---

## 2. Инфраструктура

| Параметр | Значение |
|----------|----------|
| n8n URL | `https://oburscuforring.beget.app` |
| n8n версия | 2.1.4 |
| Хостинг | Beget Cloud VPS |
| n8n логин | `6617911@mail.ru` |
| n8n пароль | В Beget Cloud панели (раздел "Приложения") |
| Webhook URL основного воркфлоу | `https://oburscuforring.beget.app/webhook/hh-events` |
| HH.RU Employer ID | `3565638` |
| Тестовая вакансия | `130853744` |
| Telegram chat ID заказчика | `295316805` |
| Bitrix24 домен | `extravert.bitrix24.ru` |
| Bitrix24 воронка | CATEGORY_ID = `97` |
| Bitrix24 stage "нанять" | `C97:UC_VBRG4F` |
| Bitrix24 stage "отказ" | `C97:3` |
| GitHub repo | `nikolayshvedchikov/my-claude-skills`, папка `hh_restapi/` |

### Токены (требуют обновления)

| Токен | Срок жизни | Как обновить |
|-------|------------|--------------|
| HH.RU user token (`USERK...`) | ~14 дней | OAuth flow на `hh.ru/oauth/authorize` с employer scope |
| Anthropic API key (`sk-ant-...`) | Бессрочно | console.anthropic.com |
| Bitrix24 webhook token | Бессрочно | Настройки → Входящие вебхуки |

---

## 3. Как работает n8n API (КРИТИЧНО — не повторять ошибки)

### 3.1 Аутентификация

```bash
# Получить сессионный cookie
curl -X POST https://oburscuforring.beget.app/rest/login \
  -H "Content-Type: application/json" \
  -d '{"emailOrUsername":"6617911@mail.ru","password":"ПАРОЛЬ"}'
# Ответ: {"data":{"token":"SESSION_TOKEN"}}
# Использовать как: Authorization: Bearer SESSION_TOKEN
```

### 3.2 Обновление воркфлоу

```bash
# PATCH, не PUT — n8n v2 использует только PATCH
curl -X PATCH https://oburscuforring.beget.app/rest/workflows/{ID} \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{...полный объект воркфлоу с актуальным versionId...}'
```

**Перед каждым PATCH обязательно:**
```bash
# Получить актуальный versionId
curl https://oburscuforring.beget.app/rest/workflows/{ID} \
  -H "Authorization: Bearer {TOKEN}"
# Взять поле .data.versionId и вставить в тело PATCH
```

### 3.3 Активация воркфлоу

```bash
# НЕ через PATCH active:true — не работает
# Только через отдельный endpoint:
curl -X POST https://oburscuforring.beget.app/rest/workflows/{ID}/activate \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"versionId":"CURRENT_VERSION_ID"}'
```

### 3.4 Создание воркфлоу

```bash
curl -X POST https://oburscuforring.beget.app/rest/workflows \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{...воркфлоу с полем "active": false...}'
# ВАЖНО: поле "active": false обязательно, иначе 500
```

---

## 4. HH.RU API — критические особенности

### 4.1 Нет webhook API

HH.RU **не предоставляет** публичный webhook API для работодателей. Эндпоинты:
- `/employers/{id}/webhooks` → 404
- `/webhooks` → 404

**Решение:** polling каждые 5 минут через отдельный воркфлоу `poller_flow.json`.

### 4.2 Переговоры (negotiations) требуют vacancy_id

```bash
# НЕ работает (возвращает 0 для employer account):
GET /negotiations

# Работает:
GET /negotiations?vacancy_id=130853744&order_by=updated_at&per_page=50
```

Поллер сначала получает список вакансий работодателя (`/employers/3565638/vacancies`), затем опрашивает переговоры по каждой вакансии отдельно.

### 4.3 Отправка сообщений кандидату

```bash
# Content-Type: application/x-www-form-urlencoded, НЕ json
POST /negotiations/{id}/messages
Content-Type: application/x-www-form-urlencoded

message=Текст+сообщения
```

В n8n нода httpRequest должна быть настроена:
- `contentType: "form-urlencoded"`
- `bodyParameters.parameters: [{name: "message", value: "..."}]`

### 4.4 Смена статуса переговоров

```bash
PUT /negotiations/{id}
Content-Type: application/x-www-form-urlencoded

status=discard  # или: approved, working, consider
```

### 4.5 Тестовая вакансия 130853744

- GET данных работает
- POST сообщений → **403 Forbidden** (это нормально для тестов)
- PUT статуса → **403 Forbidden** (нормально)
- Поэтому на нодах C4, C5, C7, D6 стоит `continueOnFail: true`

---

## 5. Claude API — критические особенности

### 5.1 Модель

Используется `claude-haiku-4-5` (не claude-3-haiku). Это важно — старые модели могут не отвечать.

### 5.2 Парсинг ответа

Claude иногда возвращает:
- Чистый JSON `{"score": 7, ...}` ← хорошо
- JSON в markdown-блоке: ` ```json\n{...}\n``` ` ← нужен regex
- JSON после вводного текста: `Я готов оценить...\n{"score": 7}` ← нужен indexOf

**Правильный трёхуровневый fallback (C2b и D5b ноды):**

```javascript
const inp = $input.item.json;
const rawText = Array.isArray(inp.content) ? inp.content[0].text : JSON.stringify(inp);
let raw = rawText.trim();
let parsed;

// Уровень 1: прямой parse (самый частый случай)
try {
  parsed = JSON.parse(raw);
} catch(e1) {
  // Уровень 2: JSON в markdown code block
  const m = raw.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
  if (m) {
    try { parsed = JSON.parse(m[1].trim()); }
    catch(e2) { throw new Error('Claude block not JSON: ' + m[1].substring(0,150)); }
  } else {
    // Уровень 3: JSON где-то в тексте
    const s = raw.indexOf('{'); const e = raw.lastIndexOf('}');
    if (s !== -1 && e > s) {
      try { parsed = JSON.parse(raw.substring(s, e+1)); }
      catch(e3) { throw new Error('No valid JSON: ' + raw.substring(0,150)); }
    } else {
      throw new Error('No JSON object in Claude response: ' + raw.substring(0,150));
    }
  }
}
```

**ПОЧЕМУ так:** Regex с `^` (anchored) не работает, когда Claude сначала пишет русский текст ("Я готов оценить..."), а потом code block. Использовать незаякоренный `/```(?:json)?\s*([\s\S]*?)\s*```/`.

### 5.3 Ссылка на данные из предыдущей ноды в Code ноде

```javascript
// Правильно:
const negData = $('C1 Получить данные отклика').first().json;

// Неправильно (теряется контекст при $input в Code ноде):
const negData = $input.first().json; // дает данные Claude, не HH.RU
```

---

## 6. n8n Code ноды — особенности

### 6.1 $input.item.json vs $input.first().json

В Code ноде при работе в цепочке:
- `$input.item.json` — текущий элемент из предыдущей ноды (в loop-контексте)
- `$input.first().json` — первый элемент (для обращения к данным HTTP-нод)
- `$('Имя ноды').first().json` — данные из конкретной ноды (самое надёжное)

### 6.2 Возврат данных из Code ноды

```javascript
// Одна запись:
return { key: value };

// Несколько записей (для следующей ноды в loop):
return [{ key: value1 }, { key: value2 }];
```

### 6.3 Static Data

```javascript
const staticData = $getWorkflowStaticData('global');
if (!staticData.negotiations) staticData.negotiations = {};
// Изменения сохраняются автоматически между выполнениями
```

---

## 7. Все баги и их фиксы (хронология)

### Bug #1: n8n API — PUT возвращает 404
**Симптом:** `PUT /rest/workflows/{id}` → 404  
**Причина:** n8n v2 использует PATCH, не PUT  
**Фикс:** Заменить все PUT на PATCH

### Bug #2: Сессия n8n истекла
**Симптом:** 401 на все API запросы  
**Причина:** Сессионный токен живёт ~24ч  
**Фикс:** `POST /rest/login` → получить новый токен

### Bug #3: Активация воркфлоу через PATCH не работает
**Симптом:** PATCH с `"active": true` → воркфлоу остаётся неактивным  
**Причина:** n8n требует отдельный endpoint для активации  
**Фикс:** `POST /rest/workflows/{id}/activate` с `{"versionId": "..."}`

### Bug #4: Создание воркфлоу → 500
**Симптом:** POST нового воркфлоу возвращает 500  
**Причина:** Отсутствовало обязательное поле `"active": false` в теле запроса  
**Фикс:** Добавить `"active": false` в объект воркфлоу перед созданием

### Bug #5: versionId mismatch
**Симптом:** n8n принимает PATCH но поведение непредсказуемо  
**Причина:** versionId в теле не совпадает с актуальным на сервере  
**Фикс:** Всегда делать GET перед PATCH, брать актуальный versionId

### Bug #6: C2b — SyntaxError "Я готов оц..."
**Симптом:** Execution падает на C2b с ошибкой JSON.parse  
**Причина:** Claude вернул русский текст перед JSON code block. Regex `/^```(?:json)?\s*/` с `^` не нашёл блок в середине строки  
**Фикс:** Убрать `^`, использовать незаякоренный: `/```(?:json)?\s*([\s\S]*?)\s*```/`

### Bug #7: C2b — "Вакансия:" unexpected token (попытка parse)
**Симптом:** Даже с исправленным regex, parse падает  
**Причина:** Строка содержала "Вакансия: Разработчик\n..." — Claude начал ответ не с JSON  
**Фикс (окончательный):** Поменять стратегию — сначала пробовать `JSON.parse(raw)` напрямую (Уровень 1), только при ошибке идти к regex (Уровень 2), затем к indexOf (Уровень 3). Уровень 1 срабатывает в большинстве случаев когда Claude возвращает чистый JSON

### Bug #8: C4 — Bad request (400) при отправке отказа
**Симптом:** POST на `/negotiations/{id}/messages` → 400  
**Причина:** Нода отправляла `Content-Type: application/json` с телом `{"text": "..."}`, но HH.RU ожидает `application/x-www-form-urlencoded` с полем `message`  
**Фикс:** Изменить `contentType: "form-urlencoded"`, `bodyParameters.parameters: [{name: "message", value: "..."}]`

### Bug #9: C5 — ссылка на несуществующую ноду
**Симптом:** Execution падает на C5 с "Node not found"  
**Причина:** URL содержал `$('C2b Разобрать ответ OpenAI')` — старое имя ноды  
**Фикс:** Обновить на `$('C2b Разобрать ответ Claude')`

### Bug #10: HH.RU /negotiations возвращает 0 откликов
**Симптом:** Поллер всегда видит 0 откликов  
**Причина:** `GET /negotiations` без параметров возвращает только переговоры соискателя, не работодателя. Работодатель обязан указать `vacancy_id`  
**Фикс:** Поллер сначала получает список вакансий `/employers/{id}/vacancies`, затем опрашивает каждую через `/negotiations?vacancy_id={id}`

---

## 8. Структура воркфлоу (47 нод основной)

### Триггеры
- `🔔 HH.RU Webhook` — основной вход от поллера и HH.RU
- `🤖 Telegram Trigger` — команды от заказчика
- `⏰ Ночной прогон 23:00` — ежедневный отчёт

### C-ветка: Первичный скрининг нового отклика
| Нода | Действие |
|------|----------|
| `🛡️ Только тестовая вакансия` | Фильтр для тестов (УДАЛИТЬ в продакшн) |
| `📍 HH Тип события` | Switch: Новый отклик / Ответ кандидата |
| `C1 Получить данные отклика` | GET `/negotiations/{id}` |
| `C2 Оценить резюме (Claude)` | POST Anthropic API |
| `C2b Разобрать ответ Claude` | Трёхуровневый JSON parse |
| `C3 score ≥ 4?` | Ветвление |
| `C4 Отправить вежливый отказ` | POST message, `continueOnFail: true` |
| `C5 Статус: Отказ` | PUT status=discard, `continueOnFail: true` |
| `C6 Сохранить в Static Data` | Инициализация диалога |
| `C7 Отправить первый вопрос` | POST message, `continueOnFail: true` |
| `C8 Статус: В рассмотрении` | PUT status=working |

### D-ветка: Диалог с кандидатом (ответ на вопрос)
| Нода | Действие |
|------|----------|
| `D1 Загрузить контекст` | Читает из Static Data по nid |
| `D1b Сохранить ответ` | Append ответа в answersGiven[] |
| `D2 Последний вопрос?` | Ветвление |
| `D3 Следующий вопрос (Claude)` | Генерирует следующий вопрос |
| `D3b Сохранить вопрос` | Append вопроса в questionsAsked[] |
| `D4 Отправить следующий вопрос` | POST message |
| `D5 Итоговая оценка (Claude)` | Финальный анализ всего диалога |
| `D5b Разобрать итоговую оценку` | Трёхуровневый JSON parse |
| `D6 Финальный статус HH` | PUT approved/discard, `continueOnFail: true` |
| `D7 Обновить сделку Битрикс24` | crm.deal.list — найти сделку |
| `D7b Обновить стадию и комментарий` | batch: deal.update + timeline.comment |
| `D8 Уведомить заказчика` | Telegram сообщение |
| `D9 Очистить состояние` | delete из Static Data |

### A-ветка: Создание вакансии через Telegram
Диалог-бриф из 4 вопросов → Claude генерирует текст → превью в Telegram с кнопками.

### B-ветка: Одобрение вакансии
Callback кнопки "Одобрить" → POST `/vacancies` на HH.RU → уведомление.

### E-ветка: Ночной отчёт
Активные вакансии → отклики за 24ч → необработанные → отчёт в Telegram.

---

## 9. Поллер (poller_flow.json)

**Логика:**
1. Schedule Trigger каждые 5 минут
2. GET `/employers/3565638/vacancies?per_page=100` — список всех вакансий
3. Для каждой вакансии: GET `/negotiations?vacancy_id={id}&order_by=updated_at&per_page=50`
4. Фильтрация новых: `updated_at > lastProcessedMap[vacancyId]` (хранится в Static Data)
5. POST на webhook основного воркфлоу для каждого нового отклика
6. Fallback: если 0 вакансий, использует тестовую вакансию `130853744`

**Важно:** При первом запуске для каждой вакансии поллер только записывает timestamp и не триггерит обработку (чтобы не засыпать всеми старыми откликами).

---

## 10. Тест-план (пошагово)

### Быстрый тест (5 минут)

```bash
# 1. Получить реальный ID переговора из тестовой вакансии
curl -H "Authorization: Bearer YOUR_HH_TOKEN" \
     -H "HH-User-Agent: HH-HR-Assistant/1.0 (n@extravert.bz)" \
     "https://api.hh.ru/negotiations?vacancy_id=130853744&per_page=5"
# Взять items[0].id

# 2. Триггернуть основной воркфлоу
curl -X POST https://oburscuforring.beget.app/webhook/hh-events \
     -H "Content-Type: application/json" \
     -d '{"type":"NEW_RESPONSE_OR_INVITATION_VACANCY","object":{"id":"ID_ИЗ_ШАГА_1","vacancy_id":"130853744"}}'

# 3. Проверить в n8n Executions — должен быть зелёный прогон
```

### Ожидаемый результат

- C1: получает данные резюме ✅
- C2: Claude возвращает JSON с оценкой ✅
- C2b: парсит JSON без ошибок ✅
- C3: ветвится по score
- C4/C7: 403 от HH.RU (нормально для тестовой), `continueOnFail` продолжает ✅
- Execution завершён зелёным ✅

### Полный E2E тест

1. С другого аккаунта HH.RU откликнуться на вакансию `130853744`
2. Подождать до 5 минут — поллер должен поймать
3. Проверить Executions в n8n
4. Если `score >= 4` — в чате HH.RU появится вопрос от бота
5. Ответить на вопрос — бот задаёт следующий (всего 3)
6. После 3-го ответа — в Telegram приходит итоговый отчёт по кандидату

---

## 11. Что делать перед продакшном

1. **Удалить** ноду `🛡️ Только тестовая вакансия` из основного воркфлоу
2. **Восстановить** соединение: `🔔 HH.RU Webhook → 📍 HH Тип события`
3. **Обновить HH.RU токен** — проверить не истёк ли (14 дней от создания)
4. **Настроить Telegram Credentials** в n8n (credential id `telegram-bot-cred`)
5. **Проверить Bitrix24** — стадии CATEGORY_ID=97 (`C97:UC_VBRG4F`, `C97:3`)
6. **Мониторить** первые 10 откликов вручную в n8n Executions

---

## 12. Как обновить HH.RU токен

HH.RU использует OAuth 2.0. Токен работодателя:

```
GET https://hh.ru/oauth/authorize?
  response_type=code&
  client_id=CLIENT_ID&
  redirect_uri=REDIRECT_URI&
  state=random_string

# Пользователь авторизуется → получаем code
# Обменять code на token:
POST https://hh.ru/oauth/token
  grant_type=authorization_code&
  client_id=CLIENT_ID&
  client_secret=CLIENT_SECRET&
  code=CODE&
  redirect_uri=REDIRECT_URI
```

После получения нового access_token — обновить во всех нодах воркфлоу через PATCH API или вручную в интерфейсе n8n.

---

## 13. Схема данных Static Data

```javascript
// Глобальный объект в Static Data основного воркфлоу
{
  negotiations: {
    "NEGOTIATION_ID": {
      nid: "string",
      vacancyId: "string",
      vacancyName: "string",
      candidateName: "string",
      resumeScore: 7,              // первичная оценка резюме
      resumeSummary: "string",
      state: "screening",
      currentQuestion: 2,          // текущий номер вопроса
      totalQuestions: 3,
      questionsAsked: ["q1", "q2"],
      answersGiven: ["a1"]
    }
  },
  briefs: {
    "CHAT_ID": {
      step: "init" | "awaiting_approval" | "done",
      chatId: "string",
      originalRequest: "string",
      answers: ["a1", "a2", "a3", "a4"],
      currentQuestion: 4,
      totalQuestions: 4,
      vacancyDraft: { name, description, salary_from, ... }
    }
  }
}

// Static Data поллера
{
  lastProcessedMap: {
    "VACANCY_ID": "2026-04-19T10:00:00+0300"  // timestamp последнего обработанного отклика
  }
}
```

---

## 14. Claude промпты (финальные версии)

### C2: Оценка резюме
```
System: Ты HR-ассистент. Оцени резюме кандидата по шкале 1-10 для данной вакансии. 
Верни JSON: {"score": number, "verdict": "pass"|"fail", "comment": "краткое пояснение", 
"rejection_text": "вежливый отказ если verdict=fail", 
"first_question": "первый квалификационный вопрос если verdict=pass"}. 
Отвечай только JSON, без markdown.
```

### D3: Следующий вопрос
```
System: Ты HR-ассистент, ведёшь квалификационный диалог с кандидатом. 
Верни JSON: {"next_question": "текст следующего вопроса"}. Только JSON, без markdown.
```

### D5: Итоговая оценка
```
System: Ты HR-ассистент. Проанализируй ответы кандидата на квалификационные вопросы. 
Верни JSON: {"final_score": number(1-10), "recommendation": "hire"|"reject", 
"summary": "краткое резюме (2-3 предложения)", "hh_status": "approved"|"discard"}. 
Только JSON, без markdown.
```

**Важно:** Даже с инструкцией "только JSON" Claude иногда добавляет вводный текст — поэтому трёхуровневый fallback обязателен.

---

## 15. Финальный статус на момент создания документа (апрель 2026)

| Компонент | Статус | Детали |
|-----------|--------|--------|
| Основной воркфлоу | ✅ ACTIVE | n8n ID: из UI |
| Поллер | ✅ ACTIVE | n8n ID: `swW1Www0gmme6Yvi` |
| Тест execution 2209 | ✅ Успешен | Кандидат score<4, отказ отправлен |
| Тест execution 2210 | ✅ Успешен | Кандидат score≥4, вопрос отправлен |
| GitHub backup | ✅ Готов | `hh_restapi/` в `my-claude-skills` |
| Продакшн готовность | ⚠️ 90% | Нужно: удалить тест-фильтр, обновить токен |

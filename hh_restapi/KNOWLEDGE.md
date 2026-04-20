# KNOWLEDGE.md — HH.RU HR Ассистент: журнал отладки и реализации

> Последнее обновление: 2026-04-20 (сессия 6). Читай этот файл перед началом работы.

---

## 1. Архитектура системы

```
HH.RU Webhook / Поллер (5 мин)
        ↓
n8n: HH.RU HR Ассистент (ID: 4LXW8oTh168CnTqy)
        ↓
[C-цепочка] Новый отклик → Claude оценивает → Accept/Reject → HH.RU
[D-цепочка] Ответ кандидата → Claude генерирует вопрос → HH.RU
[E-цепочка] Ночной прогон 23:00 → статистика + GitHub backup
[⏰] Проверка активных вакансий HH.RU — каждый час (7:00–21:00 МСК)

n8n Поллер (ID: swW1Www0gmme6Yvi) — каждые 5 минут
  → GET /employers/{employer_id}/vacancies
  → GET /negotiations/response?vacancy_id=...
  → POST webhook/hh-events если нашёл новые

УДАЛЕНО (ручное управление заказчиком):
  A-цепочка: Telegram-бриф → публикация вакансии на HH.RU
  B-цепочка: Одобрение вакансии
```

---

## 2. Credentials (продакшн: YOUR_N8N_HOST)

| Что | Значение |
|-----|----------|
| n8n URL | https://YOUR_N8N_HOST |
| n8n login field | `emailOrLdapLoginId` (НЕ emailOrUsername!) |
| n8n email | YOUR_N8N_EMAIL |
| n8n password | YOUR_N8N_PASSWORD |
| HH.RU employer ID | YOUR_EMPLOYER_ID |
| HH.RU manager ID | YOUR_MANAGER_ID |
| HH.RU token | YOUR_HH_TOKEN |
| Webhook path | /webhook/hh-events |
| Main workflow ID | 4LXW8oTh168CnTqy |
| Poller workflow ID | swW1Www0gmme6Yvi |

---

## 3. n8n API — ключевые факты

- Login: `POST /rest/login` с полем `emailOrLdapLoginId` (не `emailOrUsername`!)
- Новый n8n (>1.x) возвращает cookie `n8n-auth`, НЕ токен в теле
- Для запросов: `-b "n8n-auth=<cookie>"`
- Обновление workflow: `PATCH /rest/workflows/{id}` (не PUT!)
- Перед PATCH не нужно вручную обновлять versionId — n8n сам управляет
- executions API: ответ имеет структуру `data.results[]` (НЕ `data.data[]`)

---

## 4. HH.RU API — критические баги и факты

### ГЛАВНЫЕ БАГИ (все исправлены):

**1. Неправильный endpoint для списка откликов**
- `GET /negotiations?vacancy_id=...` — возвращает коллекцию БЕЗ `items[]`
- **Правильный:** `GET /negotiations/response?vacancy_id=...&per_page=50&page=0`

**2. Невалидный параметр сортировки**
- `order_by=updated_at` → **BAD_ARGUMENT** для `/negotiations/response`
- Убрать параметр — работает без него

**3. Смена статуса отклика (C5/C8) — action-based URL**
- `PUT /negotiations/{nid}` → **405** (endpoint для кандидатов)
- `PUT /negotiations/employer_negotiations/{nid}` → **403 wrong_state**
- **Правильный формат:**
  ```
  PUT https://api.hh.ru/negotiations/{action_id}/{nid}
  ```
  Список `action_id` берётся из `actions[].url` в ответе `GET /negotiations/{nid}`.
  - Отказ: `PUT /negotiations/discard_by_employer/{nid}` (C5)
  - Пригласить: `PUT /negotiations/invitation/{nid}` (C8)
  - HH.RU возвращает `{}` или 204 при успехе — норма

**4. Отправка сообщений кандидату (C7/D4) — form-urlencoded**
- `POST /negotiations/{nid}/messages` с JSON + поле `text` → **400 bad_argument: message**
- **Правильный формат:** `application/x-www-form-urlencoded` + поле `message`
- В n8n: `contentType: "form-urlencoded"` + `bodyParameters.parameters: [{name: "message", value: "=..."}]`
- **ВАЖНО:** `contentType: "form"` в n8n — неверное значение, body не отправляется!

### Прочие факты:
- Архивные вакансии: `POST /negotiations/{nid}/messages` → `invalid_vacancy` (сообщения нельзя слать по откликам архивных вакансий)
- `/negotiations/response` требует обязательный параметр `vacancy_id`
- `/me` для работодателя: поля `employer.id`, `employer.manager_id`

---

## 5. Webhook payload формат

HH.RU шлёт вебхуки:
```json
{"type": "NEW_RESPONSE_OR_INVITATION_VACANCY", "object": {"id": "<nid>"}}
{"type": "CHAT_MESSAGE_CREATED", "object": {"id": "<nid>"}}
```

Switch node `📍 HH Тип события`:
- `NEW_RESPONSE_OR_INVITATION_VACANCY` → "Новый отклик" (C-цепочка)
- `CHAT_MESSAGE_CREATED` → "Ответ кандидата" (D-цепочка)

Фильтр `✅ Фильтр: есть vacancy_id` проверяет `$json.body.vacancy_id !== ''`. Тестовые вызовы ДОЛЖНЫ включать `vacancy_id`.

Тестовый curl для C-цепочки:
```bash
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"type":"NEW_RESPONSE_OR_INVITATION_VACANCY","object":{"id":"NID"},"vacancy_id":"VID"}' \
  'https://YOUR_N8N_HOST/webhook/hh-events'
```

---

## 5г. Сессия 6 (2026-04-20): C7/D4 — отправка сообщений кандидату

### Баг и исправление

**Было (C7 и D4):**
```json
{"contentType": "json", "body": {"text": "=..."}}
```
→ `400 bad_argument: message` (HH.RU не знает поле `text`)

**Стало:**
```json
{
  "contentType": "form-urlencoded",
  "sendBody": true,
  "bodyParameters": {
    "parameters": [{"name": "message", "value": "=..."}]
  }
}
```
Убрать: поле `body` и заголовок `Content-Type` (n8n ставит сам).

### Диагностика n8n contentType

| Значение | Поведение |
|----------|-----------|
| `"json"` | ✅ Отправляет flat `body` object как JSON |
| `"form-urlencoded"` | ✅ Отправляет `bodyParameters.parameters[]` как form |
| `"form"` | ❌ Неверное значение — body не отправляется |

### Ограничение теста

Тестовая вакансия архивная → `invalid_vacancy` на всех вызовах `/messages`.
Полный тест C7/D4 требует активной вакансии с живым откликом.

### Состояние (конец сессии 6):
- ✅ C5: `PUT /negotiations/discard_by_employer/{nid}` — работает
- ✅ C7: `form-urlencoded` + `message` — верно, не протестировано (архив)
- ✅ C8: `PUT /negotiations/invitation/{nid}` — не тестировался
- ✅ D4: `form-urlencoded` + `message` — аналогично C7
- ✅ C2b, C3: восстановлены в продакшн (firstQuestion=`''`, threshold=4)
- ✅ Main workflow versionId: `461e8632-9f03-4b30-8f49-ed38bde3f31b`

---

## 5в. Сессия 5 (2026-04-20): C5/C8 — смена статуса HH.RU

**C5 Статус: Отказ:**
- Было: `PUT /negotiations/{nid}` + body `status=discard` → 405
- Стало: `PUT /negotiations/discard_by_employer/{nid}` (sendBody=false) ✅

**C8 Статус: В рассмотрении:**
- Было: `PUT /negotiations/{nid}` + body `status=working`
- Стало: `PUT /negotiations/invitation/{nid}` (sendBody=false)

Техническая деталь: n8n executions API → `data.results[]` (не `data.data[]`).

---

## 5б. Сессия 4 (2026-04-20, утро): включение нод, архитектура

- Включены C4/C5/C7/C8 (убраны `disabled: true`)
- Удалены A/B-цепочки (ручное управление вакансиями)
- Добавлен ⏰ Schedule Trigger (проверка вакансий каждый час)
- Обновлён фильтр: проверяет `vacancy_id !== ''`
- Поллер: умный кеш 60 мин для списка активных вакансий

D-цепочка (ответ кандидата):
```
D1 Загрузить контекст → D1b Сохранить ответ → D2 Последний вопрос?
  → D3 Следующий вопрос (Claude) → D3b → D4 Отправить вопрос
  → D5 Итоговая оценка (Claude) → D5b → D6 Финальный статус HH
  → D8 Уведомить заказчика → D9 Очистить состояние
```

---

## 6. Сессия 3 (2026-04-19): jsonBody expression mode

**КРИТИЧЕСКИЙ БАГ (исправлен):** Узлы Claude использовали `jsonBody` без префикса `=` → `{{ }}` выражения не вычислялись. Исправление: `={{ JSON.stringify({...}) }}`.

Исправлены: C2, A2, A6. Workflow реактивирован.

**ВАЖНО — Telegram Trigger:** Использует polling mode. `/webhook/{webhookId}` → 404 (нормально).

---

## 7. Сессия 2 (2026-04-19, утро): поллер

- URL: `/negotiations?` → `/negotiations/response?`
- Убран `order_by=updated_at` (BAD_ARGUMENT)
- Добавлен `onError: continueRegularOutput` на ноду вакансий
- Деактивация + реактивация для перезагрузки расписания

**ВАЖНО — n8n кеширует расписание:** После PATCH — деактивировать → реактивировать.

---

## 8. n8n — рецепт работы через Chrome MCP

```javascript
// Открыть n8n в браузере, затем через javascript_tool на странице /home/workflows:

// Получить workflow
fetch('/rest/workflows/4LXW8oTh168CnTqy')
  .then(r => r.json()).then(d => { window._wf = d.data; window._done = true; });

// Обновить workflow
fetch('/rest/workflows/4LXW8oTh168CnTqy', {
  method: 'PATCH',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    name: window._wf.name,
    nodes: window._wf.nodes,
    connections: window._wf.connections,
    settings: window._wf.settings,
    staticData: window._wf.staticData
  })
}).then(r => r.json()).then(d => { window._vid = d.data?.versionId; });

// Проверить последние executions
fetch('/rest/executions?filter=' + encodeURIComponent(JSON.stringify({workflowId:"4LXW8oTh168CnTqy"})) + '&limit=5')
  .then(r => r.json()).then(d => { window._execs = d.data.results; });
```

**ВАЖНО:** Async callbacks (`.then()`) работают только на странице `/home/workflows`, не на странице редактора workflow.

---

## 9. GitHub репо

Репо: `nikolayshvedchikov/my-claude-skills`, папка `hh_restapi/`

Файлы:
- `main_flow_ready.json` — главный workflow с плейсхолдерами
- `poller_flow.json` — поллер workflow с плейсхолдерами
- `KNOWLEDGE.md` — этот файл

**ВАЖНО:** В GitHub — плейсхолдеры (YOUR_HH_TOKEN и т.д.), не реальные токены.

---

## 10. Следующая сессия — с чего начинать

1. Прочитай этот файл
2. Открой n8n в Chrome, перейди на `/home/workflows`
3. Проверь `active=true`: `fetch('/rest/workflows/4LXW8oTh168CnTqy').then(r=>r.json()).then(d=>window._active=d.data.active)`
4. Для теста C7/D4: нужна **активная** вакансия (не архивная) + живой отклик

### Текущее состояние (конец сессии 6):
- ✅ Поллер: работает (каждые 5 минут), умный кеш 60 мин
- ✅ Главный флоу: active=true, versionId `461e8632-9f03-4b30-8f49-ed38bde3f31b`
- ✅ C-цепочка: Claude оценивает резюме → reject/accept
- ✅ C4: отправка сообщения-отказа кандидату ✅
- ✅ C5: `PUT /negotiations/discard_by_employer/{nid}` — работает
- ✅ C7: `form-urlencoded` + `message` — верно, не тест (архив вакансии)
- ✅ C8: `PUT /negotiations/invitation/{nid}` — не тестировался
- ✅ D4: `form-urlencoded` + `message` — верно, не тест
- ❓ D-цепочка: включена, не тестировалась end-to-end

### Что нужно для полного теста:
1. Активная вакансия на HH.RU (заказчик публикует)
2. Реальный отклик с score ≥ 4 → тест accept-пути (C7, C8)
3. Кандидат отвечает на сообщение → тест D-цепочки

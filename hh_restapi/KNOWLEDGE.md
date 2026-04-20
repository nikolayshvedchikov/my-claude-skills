# KNOWLEDGE.md — HH.RU HR Ассистент: журнал отладки и реализации

> Последнее обновление: 2026-04-20 (сессия 5). Читай этот файл перед началом работы.

---

## 1. Архитектура системы

```
HH.RU Webhook / Поллер (5 мин)
        ↓
n8n: HH.RU HR Ассистент (ID: 4LXW8oTh168CnTqy)
        ↓
[C-цепочка] Новый отклик → Claude оценивает → Accept/Reject → HH.RU
[D-цепочка] Telegram-ответ кандидата → Claude генерирует вопрос → HH.RU
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

## 2. Credentials (продакшн: oburscuforring.beget.app)

| Что | Значение |
|-----|----------|
| n8n URL | https://oburscuforring.beget.app |
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
1. `GET /negotiations?vacancy_id=...` — возвращает коллекцию БЕЗ `items[]`.  
   **Правильный endpoint:** `GET /negotiations/response?vacancy_id=...&per_page=50&page=0`
2. `order_by=updated_at` — **BAD_ARGUMENT** для `/negotiations/response`!  
   Этот параметр просто не поддерживается. Убери его. Работает без него.
3. **Смена статуса отклика (C5/C8)** — `PUT /negotiations/{nid}` → **405 Method Not Allowed** (это endpoint для кандидатов, не работодателей). `PUT /negotiations/employer_negotiations/{nid}` → **403 wrong_state** (тоже неверно).  
   **Правильный формат — action-based URL:**
   ```
   PUT https://api.hh.ru/negotiations/{action_id}/{nid}
   ```
   Список `action_id` берётся из поля `actions[].url` в ответе `GET /negotiations/{nid}`.  
   Пример: `PUT /negotiations/discard_by_employer/{nid}` — отказ (C5).  
   Пример: `PUT /negotiations/invitation/{nid}` — пригласить/В рассмотрении (C8).  
   HH.RU возвращает пустой `{}` или 204 при успехе — это норма.

### Остальные факты:
- `/negotiations/response` требует обязательный параметр `vacancy_id`
- `/me` для работодателя: поле `employer.id`, `employer.manager_id`
- `/vacancies?mine=true` — возвращает НЕ вакансии работодателя!
- Тестовая вакансия: `130853744` ("Начинающий специалист по внедрению Битрикс24"), архивная
- Тестовый кандидат: Данилкова Антонина, nid=5169546644, **state=discard_by_employer** (после тестов)

---

## 5. Webhook payload формат

HH.RU шлёт вебхуки в формате:
```json
{
  "type": "NEW_RESPONSE_OR_INVITATION_VACANCY",
  "object": {"id": "<negotiation_id>"}
}
```

**ВАЖНО:** n8n switch проверяет `$json.body.type == "NEW_RESPONSE_OR_INVITATION_VACANCY"`.  
В тестах нужно слать именно это значение, а не `NEW_NEGOTIATION`.

**ВАЖНО:** Фильтр `✅ Фильтр: есть vacancy_id` проверяет `$json.body.vacancy_id != ''`.  
Поллер и тестовые вызовы ДОЛЖНЫ включать `vacancy_id` в body.

Пример тестового curl:
```bash
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"type":"NEW_RESPONSE_OR_INVITATION_VACANCY","object":{"id":"NID"},"vacancy_id":"VID"}' \
  'https://YOUR_N8N_HOST/webhook/hh-events'
```

---

## 5в. Сессия 5 (2026-04-20, день): что сделано и проверено

### Исправлено: C5 и C8 — смена статуса HH.RU

**C5 Статус: Отказ** (reject path):
- Было: `PUT /negotiations/{nid}` + body `status=discard` → 405
- Стало: `PUT /negotiations/discard_by_employer/{nid}` (без body, sendBody=false)
- Проверено (execution #2488): C5 вернул `{}` без ошибок ✅
- Статус кандидата изменён на `discard_by_employer` в HH.RU ✅

**C8 Статус: В рассмотрении** (accept path):
- Было: `PUT /negotiations/{nid}` + body `status=working` → тоже дало бы 405
- Стало: `PUT /negotiations/invitation/{nid}` (без body, sendBody=false)
- Ещё не тестировалось (нет свежего кандидата в state=response)

### Техническая деталь: n8n executions API структура

В новой версии n8n ответ от `GET /rest/executions?filter=...` имеет структуру:
```
data.results[]  (НЕ data.data[])
```

### Текущее состояние системы (конец сессии 5):
- ✅ C5: исправлен, работает (`PUT /negotiations/discard_by_employer/{nid}`)
- ✅ C8: исправлен, не тестирован (`PUT /negotiations/invitation/{nid}`)
- ✅ Main workflow: active=true, versionId `8ac7ed40-8813-412c-9b42-2542c68a0c22`

---

## 5б. Сессия 4 (2026-04-20, утро): что сделано и проверено

### Сделано в сессии 4:
- **Включены C4/C5/C7/C8** — сняты `disabled: true`, воркфлоу в боевом режиме
- **Удалены A/B цепочки** — вакансии публикует заказчик вручную
- **Удалены D7/D7b** — интеграция с Битрикс24 убрана (конфликт сообщений)
- **Добавлен ⏰ Schedule Trigger** — проверка вакансий HH.RU каждый час (7:00–21:00 МСК)
- **Обновлён фильтр** — `🛡️ Только тестовая вакансия` → `✅ Фильтр: есть vacancy_id` (проверяет `!== ''`)
- **Поллер обновлён** — умный кеш 60 мин для списка активных вакансий

### n8n executions API — правильный запрос:
Фильтр `?workflowId=` НЕ работает напрямую. Нужно:
```
GET /rest/executions?filter={"workflowId":"4LXW8oTh168CnTqy"}&limit=20
```

### Важно: n8n credentials API не возвращает реальные токены
`GET /rest/credentials/{id}?includeData=true` возвращает `__n8n_BLANK...` вместо значений.
Telegram bot token недоступен через API — получить только из n8n UI.

---

## 6. Сессия 3 (2026-04-19, ~20:30 MSK): что сделано

### КРИТИЧЕСКИЙ БАГ (исправлен): jsonBody-выражения не вычислялись
Все узлы Claude (C2, A2, A6) использовали `specifyBody: "json"` с `jsonBody` без префикса `=`. В результате `{{ }}` выражения отправлялись в Claude буквально. Исправление: переключить на expression mode (`={{ JSON.stringify({...}) }}`).

### Результаты тестов (сессия 3):
- C-цепочка (execution #2324): score=2, verdict=fail, сообщение об отказе сформировано ✅
- Claude корректно оценивает пустое резюме ✅

### ВАЖНО — n8n Telegram Trigger mode:
`n8n-nodes-base.telegramTrigger` использует **polling mode** (не webhook). Путь `/webhook/{webhookId}` возвращает 404 — это нормально!

---

## 7. Поллер — проблема с вакансиями работодателя

Поллер использует `GET /employers/{id}/vacancies` — возвращает 0 активных вакансий.
Решение в сессии 4: умный кеш в staticData; главный флоу обновляет список раз в час.
После публикации реальной вакансии заказчиком — поллер подхватит её автоматически.

---

## 8. n8n login — командный рецепт

```javascript
// Через Chrome DevTools / javascript_tool на странице n8n:
fetch('/rest/workflows/4LXW8oTh168CnTqy')
  .then(r => r.json()).then(d => { window._wf = d.data; });

// Обновить workflow:
fetch('/rest/workflows/4LXW8oTh168CnTqy', {
  method: 'PATCH',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(window._wf)
}).then(r => r.json()).then(d => console.log(d.data?.versionId));
```

**Bash через curl не работает из sandbox** — proxy блокирует доступ к oburscuforring.beget.app.  
Используй Chrome MCP `javascript_tool` на вкладке с открытым n8n.

---

## 9. GitHub репо

Репо: `nikolayshvedchikov/my-claude-skills`, папка `hh_restapi/`

Файлы:
- `main_flow_ready.json` — главный workflow с плейсхолдерами
- `poller_flow.json` — поллер workflow с плейсхолдерами
- `README.md` — архитектура, тест-план, таблица замены плейсхолдеров
- `KNOWLEDGE.md` — этот файл

**ВАЖНО:** В GitHub файлы содержат ПЛЕЙСХОЛДЕРЫ (YOUR_HH_TOKEN и т.д.), не реальные токены.

---

## 10. Следующая сессия — с чего начинать

1. Прочитай этот файл
2. Открой n8n в браузере (Chrome MCP или вручную)
3. Убедись что главный флоу активен: `GET /rest/workflows/4LXW8oTh168CnTqy` → `active=true`
4. C4/C5/C7/C8 уже включены — боевой режим

### Текущее состояние системы (конец сессии 5, 2026-04-20):
- ✅ Поллер: работает (каждые 5 минут), умный кеш 60 мин
- ✅ Главный флоу: active=True, versionId `8ac7ed40-8813-412c-9b42-2542c68a0c22`
- ✅ C-цепочка: Claude оценивает резюме (score, verdict, rejection text)
- ✅ C4 Отправить отказ: сообщение кандидату в HH.RU работает
- ✅ C5 Статус: Отказ: **исправлен** — `PUT /negotiations/discard_by_employer/{nid}`
- ✅ C7 Отправить первый вопрос: включён (accept path, не тестировался)
- ✅ C8 Статус: В рассмотрении: **исправлен** — `PUT /negotiations/invitation/{nid}` (не тестировался)
- ❌ A/B-цепочки: удалены, ручное управление вакансиями
- ✅ ⏰ Проверка вакансий: каждый час (7:00–21:00 МСК)
- ❓ D-цепочка (диалог): включена, не тестировалась end-to-end

### Что нужно протестировать:
1. Accept-путь (score ≥ 4): нужен новый реальный отклик с сильным резюме
2. C8: если вернёт ошибку — смотри execution details, может потребовать body параметры
3. D-цепочка: ответ кандидата в HH.RU → диалог вопрос-ответ

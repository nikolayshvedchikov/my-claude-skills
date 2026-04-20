# KNOWLEDGE.md — HH.RU HR Ассистент: журнал отладки и реализации

> Последнее обновление: 2026-04-20 (сессия 4, утро). Читай этот файл перед началом работы.

---

## 1. Архитектура системы

```
HH.RU Webhook / Поллер (5 мин)
        ↓
n8n: HH.RU HR Ассистент (ID: 4LXW8oTh168CnTqy)
        ↓
[C-цепочка] Новый отклик → Claude оценивает → Accept/Reject → HH.RU
[D-цепочка] Telegram-ответ кандидата → Claude генерирует вопрос → HH.RU
[A-цепочка] Telegram-бриф от заказчика → Claude генерирует вакансию
[B-цепочка] Одобрение вакансии → публикация на HH.RU
[E-цепочка] Ночной прогон 23:00 → статистика + GitHub backup

n8n Поллер (ID: swW1Www0gmme6Yvi) — каждые 5 минут
  → GET /employers/3565638/vacancies
  → GET /negotiations/response?vacancy_id=...
  → POST webhook/hh-events если нашёл новые
```

---

## 2. Credentials (продакшн: oburscuforring.beget.app)

| Что | Значение |
|-----|----------|
| n8n URL | https://oburscuforring.beget.app |
| n8n login field | `emailOrLdapLoginId` (НЕ emailOrUsername!) |
| n8n email | 6617911@mail.ru |
| n8n password | YOUR_N8N_PASSWORD |
| HH.RU employer ID | 3565638 (Экстраверт) |
| HH.RU manager ID | 4424964 |
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

---

## 4. HH.RU API — критические баги и факты

### ГЛАВНЫЕ БАГИ (оба исправлены):
1. `GET /negotiations?vacancy_id=...` — возвращает коллекцию БЕЗ `items[]`.  
   **Правильный endpoint:** `GET /negotiations/response?vacancy_id=...&per_page=50&page=0`
2. `order_by=updated_at` — **BAD_ARGUMENT** для `/negotiations/response`!  
   Этот параметр просто не поддерживается. Убери его. Работает без него.

### Остальные факты:
- `/negotiations/response` требует обязательный параметр `vacancy_id`
- `/me` для работодателя: поле `employer.id` = 3565638, `employer.manager_id` = 4424964
- `/vacancies?mine=true` — возвращает НЕ вакансии работодателя (это вакансии менеджера/кандидата!)
- `/employers/3565638/vacancies/active` — у текущего аккаунта 0 активных вакансий
- Для получения вакансий работодателя: `/vacancies?manager_id={manager_id}` — НО это возвращает 859к чужих вакансий!
- Тестовая вакансия: `130853744` ("Начинающий специалист по внедрению Битрикс24"), архивная
- На архивной вакансии: 156 откликов (found: 156)
- Тестовый кандидат: Данилкова Антонина, nid=5169546644, state=response

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

**ВАЖНО:** Фильтр `🛡️ Только тестовая вакансия` проверяет `$json.body.vacancy_id`.  
Поллер и тестовые вызовы ДОЛЖНЫ включать `vacancy_id` в body.

Пример тестового curl:
```bash
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"type":"NEW_RESPONSE_OR_INVITATION_VACANCY","object":{"id":"5169546644"},"vacancy_id":"130853744"}' \
  'https://oburscuforring.beget.app/webhook/hh-events'
```

---

## 5б. Сессия 4 (2026-04-20, утро): что сделано и проверено

### Проверено (всё уже было исправлено в конце сессии 3):
1. **A7 Показать превью вакансии** — имеет `additionalFields.reply_markup` с inline-кнопками:
   ```json
   {"inline_keyboard": [[
     {"text": "✅ Одобрить", "callback_data": "approve"},
     {"text": "✏️ Изменить", "callback_data": "edit"}
   ]]}
   ```
2. **A6 Сформировать текст вакансии** — использует `claude-sonnet-4-6`, структурированный промпт с HTML-разметкой для HH.RU
3. **B1 Одобрить или изменить?** — корректно проверяет `$json.callback_query.data === 'approve'`
4. **📍 Telegram Тип** — роутит: callback_query → B1, plain message → A1

### Сделано в сессии 4:
- **Включены C4/C5/C7/C8** — сняты `disabled: true`, воркфлоу в боевом режиме (versionId: a05973fa)

### Архитектура A-цепочки (подтверждена):
```
TG Trigger → 📍 Telegram Тип
  → out[1] (text) → A1 Загрузить бриф (Code, Static Data)
    → A5 Все ответы получены?
      → out[0] (да) → A6 Claude (sonnet) → A6b → A7 (preview + кнопки)
      → out[1] (нет) → A2 Claude (haiku) → A2b → A3 Отправить вопрос
  → out[0] (callback_query) → B1 approve?
    → out[0] (approve) → B2 → B3 POST /vacancies → B4 уведомление
    → out[1] (edit) → B5 Что изменить?
```

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

### Исправлено в n8n (сессия 3):

**КРИТИЧЕСКИЙ БАГ: jsonBody-выражения не вычислялись**  
Все узлы Claude (C2, A2, A6) использовали `specifyBody: "json"` с `jsonBody` без префикса `=`. В результате `{{ }}` выражения отправлялись в Claude буквально, и Claude отвечал "Я не вижу данных из переменных шаблона" вместо JSON. Исправление: переключить на `jsonBody` с префиксом `=` (expression mode), который вычисляет `JSON.stringify({...})` с реальными данными.

1. **C2 Оценить резюме (Claude)** — `jsonBody` → expression mode (`={{ JSON.stringify({...}) }}`), модель обновлена до `claude-haiku-4-5-20251001`
2. **A2 Сгенерировать вопрос (Claude)** — то же исправление
3. **A6 Сформировать текст вакансии** — то же исправление
4. **Workflow активация** — воркфлоу был `active=False` (деактивирован в предыдущей сессии и не реактивирован). После активации webhook `/webhook/hh-events` снова вернул 200.
5. **Telegram Trigger** — UUID исправлен в предыдущей сессии: `id` = `04601f3e-a964-480b-b01d-ad5c2ed4a817`, `webhookId` = `e5fc7db0-9ce1-4d5f-82ed-3c3f564b8a99`. Работает через polling mode (не webhook).

### Результаты тестов (сессия 3):

**C-цепочка (execution #2324) — УСПЕХ:**
```json
{
  "nid": "5169546644",
  "score": 2,
  "verdict": "fail",
  "comment": "Отсутствует информация об опыте работы и навыках...",
  "rejectionText": "Уважаемая Антонина! Спасибо за интерес к вакансии...",
  "candidateName": "Данилкова Антонина",
  "vacancyName": "Начинающий специалист по внедрению Битрикс24"
}
```
- C1 → C2 (Claude) → C2b → C3 → C4(disabled) → C5(disabled) ✅
- Claude корректно оценивает пустое резюме (score=2, verdict=fail) ✅

### ВАЖНО — n8n Telegram Trigger mode:
`n8n-nodes-base.telegramTrigger` использует **polling mode** (не webhook). Путь `/webhook/{webhookId}` возвращает 404 — это нормально! n8n сам опрашивает Telegram API `getUpdates`. Не пытайся тестировать TG trigger через HTTP-запросы к webhook path.

### Текущее состояние (конец сессии 3):
- ✅ C-цепочка: полностью работает (C1→C2→C2b→C3, Claude оценивает корректно)
- ✅ Главный флоу: active=True, webhook 200
- ✅ A2/A6: исправлены expression mode jsonBody
- ✅ Telegram Trigger: polling mode, workflow активен
- ⏸️ C4/C5/C7/C8: отключены (dry mode) — нужно включить перед продакшеном
- ❓ A-цепочка: настроена, но не протестирована end-to-end (нужен реальный Telegram-бот)

---

## 6б. Сессия 2026-04-19 (сессия 2): что было сделано

### Исправлено в n8n (живой экземпляр):
1. **Поллер** — URL исправлен: `/negotiations?` → `/negotiations/response?`
2. **Поллер** — убран невалидный параметр `order_by=updated_at` (400 Bad Request)
3. **Поллер** — убран leading `=` в URL ноды `📥 Отклики по вакансии`
4. **Поллер** — добавлен `onError: continueRegularOutput` на ноду вакансий (404 не ломает цепочку)
5. **Поллер** — деактивация + реактивация для перезагрузки кешированного расписания
6. **Главный флоу** — для dry-test отключены ноды C4, C5, C7, C8 (сообщения кандидатам)
7. **Главный флоу** — E2 URL исправлен: `/negotiations?` → `/negotiations/response?`

### Результаты dry-test главного флоу (execution #2302):
- Webhook → Filter → Switch → C1 → C2(Claude) → C2b → C3 → C4(disabled) → C5(disabled)
- **C1**: успешно получил данные переговоров от HH.RU ✅
- **C2**: Claude API вызван, резюме Данилковой оценено ✅
- **C2b**: ответ Claude разобран ✅
- **C3**: score < 4 → ветка отказа ✅
- **C4/C5**: отключены → сообщения НЕ отправлены ✅ (dry run)

### Результаты dry-test поллера (execution #2305):
- Trigger → Вакансии (404, continueRegularOutput) → Извлечь IDs (fallback: 130853744) → Отклики → Фильтр (0 новых) → стоп
- **Статус**: success ✅ — все 6 нод прошли
- **Нет новых откликов**: ожидаемо — staticData.lastProcessedMap[130853744] уже на Данилковой

### ВАЖНО — n8n кеширует расписание:
После PATCH воркфлоу расписание продолжает выполнять СТАРУЮ версию из памяти.  
**Решение**: деактивировать → реактивировать:
```bash
curl -s -X POST -b "n8n-auth=<COOKIE>" https://oburscuforring.beget.app/rest/workflows/swW1Www0gmme6Yvi/deactivate
curl -s -X POST -b "n8n-auth=<COOKIE>" -H "Content-Type: application/json" -d '{"versionId":"<VID>"}' \
  https://oburscuforring.beget.app/rest/workflows/swW1Www0gmme6Yvi/activate
```

### Что ещё нужно сделать перед боевым запуском (актуально после сессии 3):
1. **Включить C4/C5/C7/C8** (убрать `disabled: true`) — перед первым боевым тестом
2. Протестировать A-цепочку: написать боту → получить вопросы → получить вакансию → одобрить → опубликовать
3. Решить проблему поллера с активными вакансиями (см. раздел 7)
4. После включения C4/C5 — протестировать отправку сообщения кандидату

---

## 7. Поллер — проблема с вакансиями работодателя

Поллер использует `GET /employers/3565638/vacancies` — но возвращает 0 активных вакансий.

Варианты решения:
- Жёстко задать список вакансий в Static Data поллера
- Использовать другой endpoint для получения вакансий менеджера
- Зарегистрировать настоящий HH.RU webhook (не поллинг)

---

## 8. n8n login — командный рецепт

```bash
# Логин (сохранить cookie)
curl -s -c /tmp/n8n_cookie.txt \
  https://oburscuforring.beget.app/rest/login \
  -H "Content-Type: application/json" \
  -d '{"emailOrLdapLoginId":"6617911@mail.ru","password":"YOUR_N8N_PASSWORD"}' > /dev/null

# Получить список воркфлоу
curl -s -b /tmp/n8n_cookie.txt \
  https://oburscuforring.beget.app/rest/workflows \
  | python3 -c "import sys,json; ws=json.load(sys.stdin); [print(w.get('id'), w.get('name','')) for w in ws.get('data',[])]"

# Получить воркфлоу
curl -s -b "n8n-auth=<COOKIE>" https://oburscuforring.beget.app/rest/workflows/4LXW8oTh168CnTqy

# Обновить воркфлоу
curl -s -X PATCH -b "n8n-auth=<COOKIE>" \
  -H "Content-Type: application/json" \
  -d '<FULL_WORKFLOW_JSON>' \
  https://oburscuforring.beget.app/rest/workflows/4LXW8oTh168CnTqy
```

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
2. Залогинься в n8n через Chrome DevTools / JS на странице n8n (Bash-curl не работает из-за proxy)
3. Убедись что главный флоу активен: `GET /rest/workflows/4LXW8oTh168CnTqy` → `active=true`
4. C4/C5/C7/C8 уже включены — боевой режим
5. **Главное:** протестируй A-цепочку — напиши в Telegram-бот, получи вопросы, одобри вакансию
6. Реши проблему поллера с активными вакансиями (раздел 7)

### Текущее состояние системы (конец сессии 4, 2026-04-20):
- ✅ Поллер: работает (каждые 5 минут)
- ✅ Главный флоу: active=True, versionId a05973fa
- ✅ C-цепочка: Claude оценивает резюме (score, verdict, rejection text)
- ✅ C4/C5/C7/C8: **ВКЛЮЧЕНЫ** — боевой режим, сообщения кандидатам будут отправляться
- ✅ A7: inline-кнопки Telegram (✅ Одобрить / ✏️ Изменить)
- ✅ A6: claude-sonnet-4-6, структурированный промпт для HH.RU вакансии
- ✅ Telegram Trigger: polling mode, workflow активен
- ❓ A-цепочка: **ещё не тестировалась end-to-end** — напиши боту и проверь
- ❓ Активные вакансии HH.RU: поллер использует fallback 130853744 (архивная)

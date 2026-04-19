# KNOWLEDGE.md — HH.RU HR Ассистент: журнал отладки и реализации

> Последнее обновление: 2026-04-19 (сессия 3, ~20:30 MSK). Читай этот файл перед началом работы.

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
| n8n password | zFP&T1Ok |
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

## 6. Сессия 3 (2026-04-19, ~20:30 MSK): что сделано

### КРИТИЧЕСКИЙ БАГ: jsonBody-выражения не вычислялись

Все узлы Claude (C2, A2, A6) использовали `specifyBody: "json"` с `jsonBody` без префикса `=`. В результате `{{ }}` выражения отправлялись в Claude буквально, и Claude отвечал "Я не вижу данных из переменных шаблона" вместо JSON.

**Исправление:** переключить на `jsonBody` с префиксом `=` (expression mode), который вычисляет `JSON.stringify({...})` с реальными данными узлов:
```
"jsonBody": "={{ JSON.stringify({ model: ..., messages: [{ content: ... + $json.field + ... }] }) }}"
```

### Что исправлено:
1. **C2 Оценить резюме (Claude)** — jsonBody → expression mode, модель → `claude-haiku-4-5-20251001`
2. **A2 Сгенерировать вопрос (Claude)** — то же исправление
3. **A6 Сформировать текст вакансии** — то же исправление
4. **Workflow активация** — воркфлоу был `active=False`. После активации `/webhook/hh-events` → 200.
5. **Telegram Trigger** — UUID исправлен (`id` = UUID, `webhookId` = UUID). Polling mode.

### Результат теста C-цепочки (execution #2324) — УСПЕХ:
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

### ВАЖНО — n8n Telegram Trigger: polling mode, не webhook
`n8n-nodes-base.telegramTrigger` использует **polling mode**. Путь `/webhook/{webhookId}` → 404 — это нормально! n8n сам опрашивает `getUpdates`. Не тестируй TG trigger через HTTP POST к webhook path.

### Текущее состояние (конец сессии 3):
- ✅ C-цепочка: C1→C2→C2b→C3 работает (score, verdict, rejection text)
- ✅ Главный флоу: active=True, webhook /webhook/hh-events → 200
- ✅ C2/A2/A6: jsonBody expression mode исправлен
- ✅ Telegram Trigger: polling mode, UUID/webhookId корректны
- ⏸️ C4/C5/C7/C8: отключены (dry mode)
- ❓ A-цепочка: не тестировалась end-to-end
- ❓ Активные вакансии HH.RU: поллер использует fallback 130853744

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
- C1: успешно получил данные переговоров от HH.RU ✅
- C2: Claude API вызван, резюме Данилковой оценено ✅
- C2b: ответ Claude разобран ✅
- C3: score < 4 → ветка отказа ✅
- C4/C5: отключены → сообщения НЕ отправлены ✅ (dry run)

### ВАЖНО — n8n кеширует расписание:
После PATCH воркфлоу расписание выполняет СТАРУЮ версию из памяти.  
**Решение**: деактивировать → реактивировать:
```bash
curl -s -X POST -b "n8n-auth=<COOKIE>" https://oburscuforring.beget.app/rest/workflows/swW1Www0gmme6Yvi/deactivate
curl -s -X POST -b "n8n-auth=<COOKIE>" -H "Content-Type: application/json" -d '{"versionId":"<VID>"}' \
  https://oburscuforring.beget.app/rest/workflows/swW1Www0gmme6Yvi/activate
```

### Что нужно сделать перед боевым запуском:
1. **Включить C4/C5/C7/C8** (убрать `disabled: true`) — перед первым боевым тестом
2. Протестировать A-цепочку: написать боту → вопросы → вакансия → одобрить → опубликовать
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
  -d '{"emailOrLdapLoginId":"6617911@mail.ru","password":"zFP&T1Ok"}' > /dev/null

COOKIE=$(grep 'n8n-auth' /tmp/n8n_cookie.txt | awk '{print $NF}')

# Получить список воркфлоу
curl -s -b "n8n-auth=$COOKIE" https://oburscuforring.beget.app/rest/workflows \
  | python3 -c "import sys,json; [print(w['id'], w['name']) for w in json.load(sys.stdin)['data']]"

# Получить воркфлоу
curl -s -b "n8n-auth=$COOKIE" https://oburscuforring.beget.app/rest/workflows/4LXW8oTh168CnTqy

# Обновить воркфлоу (PATCH)
curl -s -X PATCH -b "n8n-auth=$COOKIE" \
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
2. Залогинься в n8n через cookie (раздел 8)
3. Убедись что главный флоу активен: `GET /rest/workflows/4LXW8oTh168CnTqy` → `active=true`
4. Если нужен продакшн: включи C4/C5/C7/C8 — убери `"disabled": true` у этих нод через PATCH
5. Протестируй A-цепочку: напиши в Telegram-бот, убедись что получаешь вопросы и вакансию
6. Реши проблему поллера с активными вакансиями (раздел 7)

### Текущее состояние системы (конец сессии 3):
- ✅ Поллер: работает (каждые 5 минут, execution 2326 — success)
- ✅ Главный флоу: active=True, versionId ~31f38491
- ✅ C-цепочка: Claude оценивает резюме (score, verdict, rejection text)
- ✅ C2/A2/A6: исправлен jsonBody expression mode
- ✅ Telegram Trigger: polling mode, UUID/webhookId корректны
- ⏸️ C4/C5/C7/C8: отключены (dry mode)
- ❓ A-цепочка: не тестировалась end-to-end
- ❓ Активные вакансии HH.RU: не найдены через API, поллер использует fallback 130853744

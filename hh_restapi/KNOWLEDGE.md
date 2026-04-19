# KNOWLEDGE.md — HH.RU HR Ассистент: журнал отладки и реализации

> Последнее обновление: 2026-04-19 (сессия 2, ~22:00 MSK). Читай этот файл перед началом работы.

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
  → GET /employers/{employer_id}/vacancies (fallback: hardcoded vacancy)
  → GET /negotiations/response?vacancy_id=...&per_page=50&page=0
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
| HH.RU token | USERK2LG6I3D4C3JH9BJ6IO6BJVBM5OONJDARBHTO9PBJE277OIMIAOVJCC9PMDL |
| Webhook path | /webhook/hh-events |
| Main workflow ID | 4LXW8oTh168CnTqy |
| Poller workflow ID | swW1Www0gmme6Yvi |

---

## 3. n8n API — ключевые факты

- Login: `POST /rest/login` с полем `emailOrLdapLoginId` (не `emailOrUsername`!)
- Новый n8n (>1.x) возвращает cookie `n8n-auth`, НЕ токен в теле
- Для запросов: `-b "n8n-auth=<cookie>"`
- Обновление workflow: `PATCH /rest/workflows/{id}` (не PUT!)
- Деактивация: `POST /rest/workflows/{id}/deactivate`
- Активация: `POST /rest/workflows/{id}/activate` с телом `{"versionId":"<VID>"}`
- **ВАЖНО**: после PATCH расписание не перезагружается — нужна деактивация + активация!

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
- `/employers/3565638/vacancies` — возвращает 0 активных вакансий (404 not_found или пустой список)
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

## 6. Сессия 2026-04-19: что сделано

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
VID=$(curl -s -b "n8n-auth=<COOKIE>" https://oburscuforring.beget.app/rest/workflows/swW1Www0gmme6Yvi | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['versionId'])")
curl -s -X POST -b "n8n-auth=<COOKIE>" -H "Content-Type: application/json" -d "{\"versionId\":\"$VID\"}" \
  https://oburscuforring.beget.app/rest/workflows/swW1Www0gmme6Yvi/activate
```

### Что ещё нужно сделать перед боевым запуском:
1. Включить C4/C5/C7/C8 обратно (убрать `disabled: true`)
2. Протестировать отправку сообщения Данилковой в рабочее время (с её согласия)
3. Убедиться что HH.RU webhook шлёт `NEW_RESPONSE_OR_INVITATION_VACANCY`
4. Решить проблему поллера с активными вакансиями (см. раздел 7)
5. Проверить Bitrix24 и Telegram интеграции

---

## 7. Поллер — проблема с вакансиями работодателя

Поллер использует `GET /employers/3565638/vacancies` — но возвращает 0 активных вакансий.  
Код-нода `🔢 Извлечь ID вакансий` автоматически использует fallback: `vacancy_id = '130853744'`.

Варианты долгосрочного решения:
- Жёстко задать список активных вакансий в Static Data поллера
- Использовать другой endpoint для получения вакансий менеджера
- Зарегистрировать настоящий HH.RU webhook (не поллинг) — тогда поллер не нужен вообще

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

# Деактивировать воркфлоу
curl -s -X POST -b "n8n-auth=$COOKIE" \
  https://oburscuforring.beget.app/rest/workflows/swW1Www0gmme6Yvi/deactivate

# Активировать воркфлоу (нужен versionId)
VID=$(curl -s -b "n8n-auth=$COOKIE" https://oburscuforring.beget.app/rest/workflows/swW1Www0gmme6Yvi \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['versionId'])")
curl -s -X POST -b "n8n-auth=$COOKIE" -H "Content-Type: application/json" \
  -d "{\"versionId\":\"$VID\"}" \
  https://oburscuforring.beget.app/rest/workflows/swW1Www0gmme6Yvi/activate
```

---

## 9. GitHub репо

Репо: `nikolayshvedchikov/my-claude-skills`, папка `hh_restapi/`

Файлы:
- `main_flow_ready.json` — главный workflow с плейсхолдерами
- `poller_flow.json` — поллер workflow (6-нодовый, с плейсхолдерами)
- `README.md` — архитектура, тест-план, таблица замены плейсхолдеров
- `KNOWLEDGE.md` — этот файл

**ВАЖНО:** В GitHub файлы содержат ПЛЕЙСХОЛДЕРЫ (YOUR_HH_TOKEN и т.д.), не реальные токены.

---

## 10. Следующая сессия — с чего начинать

1. Прочитай этот файл
2. Залогинься в n8n через cookie (раздел 8)
3. Включи C4/C5/C7/C8 обратно: PATCH главного флоу, убери `"disabled": true` у этих нод
4. После PATCH — деактивируй и реактивируй главный флоу (раздел 6, блок n8n кеш)
5. Реши проблему поллера с активными вакансиями: либо хардкод вакансий в staticData, либо HH.RU webhook
6. Протестируй с Данилковой в рабочее время (попроси её ответить на новое тестовое сообщение)
7. Проверь что HH.RU webhook шлёт правильный тип события

### Текущее состояние системы (конец сессии 2):
- ✅ Поллер: работает (execution 2305 — success, все 6 нод)
- ✅ Главный флоу: работает в dry-mode (C4/C5/C7/C8 отключены)
- ✅ Claude оценивает резюме корректно
- ✅ staticData поллера: lastProcessedMap[130853744] = 2026-04-16T09:32:06+0300
- ⏸️ Отправка кандидатам: отключена (dry mode)
- ❓ Активные вакансии HH.RU: не найдены через API, поллер использует fallback 130853744

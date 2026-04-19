# KNOWLEDGE.md — HH.RU HR Ассистент: журнал отладки и реализации

> Последнее обновление: 2026-04-19. Читай этот файл перед началом работы.

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
- Перед PATCH не нужно вручную обновлять versionId — n8n сам управляет

---

## 4. HH.RU API — критические баги и факты

### ГЛАВНЫЙ БАГ (исправлен 2026-04-19):
`GET /negotiations?vacancy_id=...` — возвращает коллекцию БЕЗ `items[]`.  
**Правильный endpoint:** `GET /negotiations/response?vacancy_id=...&order_by=updated_at&per_page=50&page=0`

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

## 6. Сессия 2026-04-19: что сделано

### Исправлено в n8n (живой экземпляр):
1. **Поллер** — URL исправлен: `/negotiations?` → `/negotiations/response?`
2. **Главный флоу** — для dry-test отключены ноды C4, C5, C7, C8 (сообщения кандидатам)
3. **Главный флоу** — E2 URL исправлен: `/negotiations?` → `/negotiations/response?`

### Результаты dry-test (execution #2294):
- Webhook → Filter → Switch → C1 → C2(Claude) → C2b → C3 → C4(disabled) → C5(disabled)
- **C1**: успешно получил данные переговоров от HH.RU ✅
- **C2**: Claude API вызван, резюме Данилковой оценено ✅
- **C2b**: ответ Claude разобран ✅
- **C3**: score < 4 → ветка отказа ✅
- **C4/C5**: отключены → сообщения НЕ отправлены ✅ (dry run)

### Что ещё нужно сделать перед боевым запуском:
1. Убедиться что HH.RU webhook реально шлёт `NEW_RESPONSE_OR_INVITATION_VACANCY` (или обновить condition в Switch)
2. Поллер: `/employers/3565638/vacancies` возвращает 0 активных вакансий → нужно найти правильный способ получения вакансий работодателя
3. Поллер должен включать `vacancy_id` в payload при вызове webhook
4. Включить C4/C5/C7/C8 обратно для боевой работы
5. Протестировать с Данилковой Антониной в рабочее время (не воскресенье)
6. Проверить Bitrix24 и Telegram интеграции

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
2. Залогинься в n8n через cookie
3. Включи C4/C5/C7/C8 обратно (убери `disabled: true`)
4. Реши проблему поллера с вакансиями
5. Убедись что HH.RU webhook тип совпадает со switch condition
6. Протестируй с Данилковой в рабочее время

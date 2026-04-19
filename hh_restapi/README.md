# HH.RU AI-HR Ассистент — n8n + Claude + Telegram + Bitrix24

Автоматизированный HR-ассистент: получает отклики с HH.RU, оценивает резюме через Claude AI, ведёт квалификационный диалог с кандидатом, обновляет статусы в HH.RU и Bitrix24, уведомляет заказчика в Telegram.

---

## Файлы

| Файл | Описание |
|------|----------|
| `main_flow_ready.json` | Основной n8n воркфлоу (47 нод) |
| `poller_flow.json` | Поллер — опрашивает HH.RU каждые 5 минут |
| `KNOWLEDGE.md` | Полный разбор реализации, все баги и фиксы |

---

## Архитектура

```
[HH.RU Poller, 5 мин]
        ↓ POST webhook
[n8n: 🔔 HH.RU Webhook]
        ↓
[🛡️ Фильтр тестовой вакансии]  ← УДАЛИТЬ перед продакшном
        ↓
[📍 Тип события: Новый отклик / Ответ кандидата]
        ↓
  ┌─────────────┐         ┌────────────────────┐
  │ C: Скрининг │         │ D: Диалог с кандидатом│
  │ C1 GET nego │         │ D1 загрузить контекст│
  │ C2 Claude   │         │ D2 последний вопрос? │
  │ C2b parse   │         │ D3 след. вопрос      │
  │ C3 score≥4? │         │ D5 итоговая оценка   │
  │ C4 отказ    │         │ D6 статус HH         │
  │ C6 save     │         │ D7 Bitrix24          │
  │ C7 вопрос   │         │ D8 Telegram          │
  └─────────────┘         └────────────────────┘

[Telegram Trigger]
        ↓
  ┌──────────────────┐    ┌──────────────────────┐
  │ A: Создать вакансию│  │ B: Одобрить/изменить │
  │ (диалог с HR)    │    │ (callback кнопки)    │
  └──────────────────┘    └──────────────────────┘

[⏰ Ночной прогон 23:00]
        ↓
  E1→E2→E3→E5: отчёт в Telegram
```

---

## Инфраструктура

| Компонент | Значение |
|-----------|----------|
| n8n instance | `https://oburscuforring.beget.app` (Beget Cloud VPS) |
| n8n версия | 2.1.4 |
| Webhook URL | `https://oburscuforring.beget.app/webhook/hh-events` |
| Employer ID HH.RU | `3565638` |
| Тестовая вакансия | `130853744` |
| Telegram chat ID | `295316805` |
| Bitrix24 | `extravert.bitrix24.ru`, воронка CATEGORY_ID=97 |

---

## Статус (апрель 2026)

- ✅ Основной воркфлоу активен, протестирован (executions 2209, 2210)
- ✅ Поллер активен (ID: `swW1Www0gmme6Yvi`), опрашивает каждые 5 мин
- ✅ Claude JSON parsing — трёхуровневый fallback
- ⚠️ HH.RU токен истекает через ~14 дней от даты получения (нужен refresh)
- ⚠️ Нода `🛡️ Только тестовая вакансия` — удалить перед продакшном

---

## План тестирования

### Шаг 1. Убедиться, что воркфлоу активны

1. Зайти в n8n: `https://oburscuforring.beget.app`
2. Логин: `6617911@mail.ru` / пароль из Beget Cloud панели
3. Проверить, что оба воркфлоу в статусе **Active**:
   - `HH.RU HR Ассистент`
   - `HH.RU Poller — Новые отклики`

### Шаг 2. Тест нового отклика (ручной)

Отправить POST на webhook вручную:

```bash
curl -X POST https://oburscuforring.beget.app/webhook/hh-events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "NEW_RESPONSE_OR_INVITATION_VACANCY",
    "object": {
      "id": "REAL_NEGOTIATION_ID",
      "vacancy_id": "130853744"
    }
  }'
```

**Где взять `REAL_NEGOTIATION_ID`:**
```bash
curl -H "Authorization: Bearer YOUR_HH_TOKEN" \
     -H "HH-User-Agent: HH-HR-Assistant/1.0 (n@extravert.bz)" \
     "https://api.hh.ru/negotiations?vacancy_id=130853744&per_page=5"
```
Взять любой `id` из `items[]`.

**Ожидаемый результат:**
1. n8n execution запустился
2. C1 получил данные отклика от HH.RU
3. C2 отправил резюме в Claude, получил JSON с `score`, `verdict`
4. Если `score >= 4` → C6 сохранил в Static Data, C7 попытался отправить вопрос (403 для тестовой — это нормально, `continueOnFail: true`)
5. Если `score < 4` → C4 попытался отправить отказ (403 — норма), C5 сменил статус

### Шаг 3. Тест автоматического поллера

1. Создать новый реальный отклик на вакансию 130853744 с другого аккаунта HH
2. Подождать до 5 минут
3. Поллер должен его поймать и отправить в основной воркфлоу
4. Проверить в n8n → Executions

### Шаг 4. Тест диалога с кандидатом (D-ветка)

Если кандидат прошёл скрининг (score ≥ 4) и реально написал ответ в чате HH.RU:
```bash
curl -X POST https://oburscuforring.beget.app/webhook/hh-events \
  -H "Content-Type: application/json" \
  -d '{
    "type": "CHAT_MESSAGE_CREATED",
    "object": {"id": "NEGOTIATION_ID"},
    "message": {"text": "Ответ кандидата здесь", "author": {"participant_type": "APPLICANT"}}
  }'
```

### Шаг 5. Выход в продакшн

1. В основном воркфлоу удалить ноду `🛡️ Только тестовая вакансия` (или изменить условие на `vacancy_id != ''`)
2. Восстановить прямое соединение: `🔔 HH.RU Webhook → 📍 HH Тип события`
3. Обновить HH.RU токен (если истёк)
4. Мониторить первые 10 реальных откликов вручную

---

## Замена токенов перед импортом

В JSON-файлах все токены заменены на плейсхолдеры. Перед импортом в n8n заменить:

| Плейсхолдер | Что подставить |
|-------------|----------------|
| `YOUR_HH_TOKEN` | Bearer token из HH.RU OAuth (employer) |
| `YOUR_ANTHROPIC_KEY` | API key из console.anthropic.com |
| `YOUR_EMPLOYER_ID` | ID работодателя на HH.RU |
| `YOUR_TEST_VACANCY_ID` | ID тестовой вакансии |
| `YOUR_N8N_WEBHOOK_URL` | URL вебхука основного воркфлоу |
| `YOUR_TELEGRAM_CHAT_ID` | Telegram chat ID для уведомлений |
| `YOUR_BITRIX24_DOMAIN` | Домен Bitrix24 |
| `YOUR_WEBHOOK` | Токен вебхука Bitrix24 REST |
| `your@email.com` | Email для HH-User-Agent |

# Bitrix24 Vibecode — База знаний

## Документация
- https://vibecode.bitrix24.tech/docs

## Что такое Vibecode
Vibecode — специальный режим и API Bitrix24, разработанный для AI-инструментов (Claude, Cursor, Copilot, Codex и т.д.). Позволяет AI-агентам работать с Bitrix24 через стандартный MCP-протокол (Model Context Protocol).

## MCP-сервер Bitrix24

### Подключение к Claude Desktop
Добавить в `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "bitrix24": {
      "command": "npx",
      "args": ["-y", "@bitrix24/mcp-server"],
      "env": {
        "BITRIX24_WEBHOOK_URL": "https://YOUR_DOMAIN.bitrix24.ru/rest/USER_ID/WEBHOOK_TOKEN/"
      }
    }
  }
}
```

### Установка MCP-сервера вручную
```bash
npm install -g @bitrix24/mcp-server
# или через npx (автоматически)
npx @bitrix24/mcp-server
```

## Возможности Vibecode API
- Прямой доступ ко всем REST-методам Bitrix24 через MCP
- Работа с CRM, задачами, пользователями через естественный язык
- Генерация кода для интеграций с Bitrix24
- Автоматизация без написания кода вручную

## Ключевые инструменты MCP
После подключения Claude получает доступ к инструментам:
- `bitrix24_call` — вызов любого REST-метода
- `bitrix24_crm_*` — работа с CRM
- `bitrix24_task_*` — работа с задачами

## Webhook URL
Формат:
```
https://YOUR_DOMAIN.bitrix24.ru/rest/USER_ID/WEBHOOK_TOKEN/
```
Получить: Bitrix24 → Разработчикам → Другое → Входящий вебхук

## Работа через AI (типичные сценарии)

### Создание кода интеграции
Описать задачу Claude: "Создай Python-скрипт для синхронизации сделок из Bitrix24 в Google Sheets"

### Автоматизация через MCP
С подключённым MCP-сервером можно:
- "Покажи мне все открытые сделки"
- "Создай лид с данными: имя Иван, телефон +79001234567"
- "Обнови стадию сделки ID 123 на 'Выиграна'"

## Особенности
- Vibecode работает поверх стандартного REST API Bitrix24
- MCP-сервер использует входящий вебхук для авторизации
- Поддерживается Claude Code, Claude Desktop, Cursor, VS Code (Copilot)

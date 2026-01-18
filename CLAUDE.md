# YourBody PRO - Project Instructions for Claude

## Project Overview
YourBody PRO is a Telegram bot with WebApp for habit tracking (food, sleep, weekly reviews).

## Architecture
- **Telegram Bot**: Python (aiogram) - `app.py`, `habit_handlers.py`
- **WebApp Frontend**: React + TypeScript + Vite - `webapp/frontend/`
- **WebApp Backend**: FastAPI - `webapp/backend/`
- **Database**: SQLite - `bot.db`

## Deployment
- **Frontend**: Vercel (auto-deploys from GitHub)
- **Backend**: VPS at `217.198.6.249` (systemd service `yourbody-backend`)
- **Bot**: VPS at `217.198.6.249` (systemd service `yourbody-bot`)

## Important Instructions

### After completing any task:
1. **Commit and push changes** to GitHub
2. **Restart backend on server** (if backend was modified):
   ```bash
   ssh root@217.198.6.249 "cd /root/yourbody-pro && git pull origin main && sudo systemctl restart yourbody-backend"
   ```
3. **Restart bot on server** (if bot was modified):
   ```bash
   ssh root@217.198.6.249 "cd /root/yourbody-pro && git pull origin main && sudo systemctl restart yourbody-bot"
   ```
4. **Frontend auto-deploys** via Vercel when pushed to GitHub

### Git Commit Format
Always end commits with:
```
Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```

### Key Files
- `webapp/frontend/src/` - React components, pages, hooks
- `webapp/backend/main.py` - FastAPI endpoints
- `webapp/frontend/index.html` - Must include Telegram WebApp SDK script
- `.env` - Environment variables (BOT_TOKEN, API keys)

### Environment Variables
```
BOT_TOKEN=<telegram_bot_token>
ANTHROPIC_API_KEY=<api_key>
YOOKASSA_SHOP_ID=<shop_id>
YOOKASSA_SECRET_KEY=<secret>
DEBUG=false
```

### Common Issues
- If auth fails in WebApp: Check that `telegram-web-app.js` script is in `index.html`
- If backend unreachable: Check CORS settings in `main.py`
- If SSH fails: VPN may be required or server temporarily unavailable

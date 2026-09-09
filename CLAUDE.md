# YourBody PRO - Project Instructions for Claude

## Project Overview
YourBody PRO is a Telegram bot with WebApp for habit tracking (food, sleep, weekly reviews).

## Architecture
- **Telegram Bot**: Python (aiogram) - `app.py`, `habit_handlers.py`
- **WebApp Frontend**: React + TypeScript + Vite - `webapp/frontend/`
- **WebApp Backend**: FastAPI - `webapp/backend/`
- **Database**: SQLite - `bot.db`

## Deployment
- **Frontend**: VPS at `https://app.pasekaproduction.ru:9443` (HTTPS gateway), with nginx also serving port 443. The legacy Vercel hostname redirects navigation to the VPS.
- **Backend**: VPS at `5.35.126.42` (systemd service `yourbody-api`)
- **Bot**: VPS at `5.35.126.42` (systemd service `tg-bot`)
- **Server path**: `/opt/yourbody-pro`

## Important Instructions

### After completing any task:
1. **Commit and push changes** to GitHub
2. **Restart backend on server** (if backend was modified):
   ```bash
   ssh root@5.35.126.42 "cd /opt/yourbody-pro && git pull origin main && systemctl restart yourbody-api"
   ```
3. **Restart bot on server** (if bot was modified):
   ```bash
   ssh root@5.35.126.42 "cd /opt/yourbody-pro && git pull origin main && systemctl restart tg-bot"
   ```
4. **Frontend deployment**: run the browser tests/build locally, back up the server's `webapp/frontend/dist`, and copy the tested build there. GitHub/Vercel auto-deployment only updates the legacy redirect; it does not deploy the VPS build.
5. **Outbound connections**: the API and habit workers need `OUTBOUND_PROXY_URL=socks5://127.0.0.1:1080` and the `httpx[socks]` dependency on this VPS. Direct Telegram connections time out; direct OpenRouter connections are rejected.

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

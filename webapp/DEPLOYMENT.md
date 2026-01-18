# Развёртывание Habit Tracker WebApp

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                        VPS                               │
│  ┌─────────────────┐  ┌─────────────────────────────┐   │
│  │   Nginx         │  │  Python Services            │   │
│  │   (reverse      │  │  ┌───────────────────────┐  │   │
│  │    proxy)       │  │  │ app.py (Telegram bot) │  │   │
│  │                 │  │  │ + habit_handlers.py   │  │   │
│  │  :443 → :8000   │  │  └───────────────────────┘  │   │
│  │  :443 → :3000   │  │  ┌───────────────────────┐  │   │
│  │                 │  │  │ FastAPI backend       │  │   │
│  └─────────────────┘  │  │ (webapp/backend)      │  │   │
│                       │  │ :8000                 │  │   │
│                       │  └───────────────────────┘  │   │
│  ┌─────────────────┐  │                             │   │
│  │ React Frontend  │  │  ┌───────────────────────┐  │   │
│  │ (static files)  │  │  │ SQLite Database       │  │   │
│  │ served by Nginx │  │  │ bot.db                │  │   │
│  └─────────────────┘  │  └───────────────────────┘  │   │
└─────────────────────────────────────────────────────────┘
```

## Требования

- VPS с Ubuntu 22.04+ (минимум 1GB RAM)
- Python 3.10+
- Node.js 18+
- Nginx
- Домен с SSL сертификатом (для Telegram WebApp обязателен HTTPS)

## 1. Настройка сервера

### Установка зависимостей

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Python
sudo apt install python3.10 python3.10-venv python3-pip -y

# Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install nodejs -y

# Nginx
sudo apt install nginx -y

# Certbot для SSL
sudo apt install certbot python3-certbot-nginx -y
```

### Создание директорий

```bash
sudo mkdir -p /opt/tg-bot
sudo chown $USER:$USER /opt/tg-bot
```

## 2. Развёртывание бота

```bash
# Клонируем/копируем проект
cd /opt/tg-bot

# Создаём виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости бота
pip install aiogram aiosqlite yookassa python-dotenv

# Устанавливаем зависимости webapp backend
pip install -r webapp/backend/requirements.txt

# Копируем .env файл и настраиваем
cp .env.example .env
nano .env
```

### Настройка .env

```env
# Telegram Bot
BOT_TOKEN=your_bot_token
GROUP_ID=-100xxxxxxxxxx
ADMIN_IDS=123456789

# YooKassa
SHOP_ID=xxxxxx
SHOP_SECRET_KEY=live_xxxxx
MONTH_PRICE=3690

# Habit Tracker
WEBAPP_URL=https://yourdomain.com
OPENROUTER_API_KEY=sk-or-xxxxxxxxxxxx
DEBUG=false

# Database
DB_PATH=/opt/tg-bot/bot.db
```

## 3. Сборка фронтенда

```bash
cd /opt/tg-bot/webapp/frontend

# Устанавливаем зависимости
npm install

# Собираем продакшн версию
npm run build

# Результат в /opt/tg-bot/webapp/frontend/dist
```

## 4. Настройка Nginx

```bash
sudo nano /etc/nginx/sites-available/yourbody
```

```nginx
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Frontend (статика)
    location / {
        root /opt/tg-bot/webapp/frontend/dist;
        try_files $uri $uri/ /index.html;

        # Кэширование статики
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
            expires 30d;
            add_header Cache-Control "public, immutable";
        }
    }

    # Backend API
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (если понадобится)
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeout для LLM запросов
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/yourbody /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 5. SSL сертификат

```bash
sudo certbot --nginx -d yourdomain.com
```

## 6. Systemd сервисы

### Telegram бот

```bash
sudo nano /etc/systemd/system/yourbody-bot.service
```

```ini
[Unit]
Description=YourBody Telegram Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/tg-bot
Environment="PATH=/opt/tg-bot/venv/bin"
ExecStart=/opt/tg-bot/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### FastAPI backend

```bash
sudo nano /etc/systemd/system/yourbody-api.service
```

```ini
[Unit]
Description=YourBody Habit Tracker API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/tg-bot/webapp/backend
Environment="PATH=/opt/tg-bot/venv/bin"
ExecStart=/opt/tg-bot/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Запуск сервисов

```bash
sudo systemctl daemon-reload
sudo systemctl enable yourbody-bot yourbody-api
sudo systemctl start yourbody-bot yourbody-api
```

## 7. Настройка Telegram Mini App

### В BotFather

1. Откройте @BotFather
2. `/mybots` → выберите бота → `Bot Settings` → `Menu Button`
3. Установите URL: `https://yourdomain.com`
4. Или используйте `Configure Mini App` для более детальной настройки

### Проверка

1. Откройте бота
2. Нажмите кнопку меню или отправьте `/habits`
3. Должно открыться веб-приложение

## 8. Мониторинг

### Просмотр логов

```bash
# Бот
sudo journalctl -u yourbody-bot -f

# API
sudo journalctl -u yourbody-api -f

# Nginx
sudo tail -f /var/log/nginx/error.log
```

### Проверка статуса

```bash
sudo systemctl status yourbody-bot
sudo systemctl status yourbody-api
```

## Обновление

```bash
cd /opt/tg-bot

# Обновляем код
git pull  # или копируем новые файлы

# Обновляем зависимости
source venv/bin/activate
pip install -r webapp/backend/requirements.txt

# Пересобираем фронтенд
cd webapp/frontend
npm install
npm run build

# Перезапускаем сервисы
sudo systemctl restart yourbody-bot yourbody-api
```

## Бюджет

| Компонент | Стоимость/месяц |
|-----------|-----------------|
| VPS (1GB RAM) | $5-10 |
| Домен | $1-2 |
| OpenRouter (GPT-4o) | ~$5-20 (зависит от использования) |
| **Итого** | **~$11-32/мес** |

### Оптимизация расходов на LLM

- Используйте `gpt-4o-mini` для текстового анализа (~10x дешевле)
- Кэшируйте результаты анализа
- Ограничьте количество запросов на пользователя в день

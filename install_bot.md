# Dion-bot

Dion Бот для оповещения zabbix alert

Установка Python
На сервере:
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
mkdir -p /opt/dion-zabbix-bot
cd /opt/dion-zabbix-bot
python3 -m venv venv
source venv/bin/activate
pip install flask requests python-dotenv




Файл .env
Создай файл /opt/dion-zabbix-bot/.env
BOT_EMAIL=bot@example.local
BOT_PASSWORD=password
BOT_NAME=Zabbix Dion Bot
BIND_HOST=0.0.0.0
BIND_PORT=8080  #( выбираем любой порт )
DEFAULT_PARSE_MODE=Markdown
STATE_FILE=/opt/dion-zabbix-bot/state.json



Запуск в ручном режиме 
cd /opt/dion-zabbix-bot
source venv/bin/activate
python3 bot.py


Найди бота в Dion
Напиши ему /start
Или добавь его в группу и тоже напиши /start
После этого бот запомнит chat_id.

Проверить, какие чаты подключены к боту :

curl http://127.0.0.1:8080/debug/chats


Проверка вручную
Как полчучишь chat_id, можно руками проверить отправку алерта:

curl -X POST http://127.0.0.1:8080/zabbix \
  -H 'Content-Type: application/json' \
  -d '{
    "chat_id": "UUID_ЧАТА",
    "subject": "Problem: Linux host is unavailable",
    "message": "Host: srv-monitor-01\nTrigger: ICMP ping failed\nTime: 2026-03-06 12:30:00",
    "severity": "High",
    "host": "srv-monitor-01",
    "event_id": "123456"
  }'



Для работы бота в автоматическом режиме 

Создать  nano /etc/systemd/system/dion-zabbix-bot.service

[Unit]
Description=Dion Zabbix Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/dion-zabbix-bot
EnvironmentFile=/opt/dion-zabbix-bot/.env
ExecStart=/opt/dion-zabbix-bot/venv/bin/python /opt/dion-zabbix-bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target


после запустить команды для запуска

sudo systemctl daemon-reload
sudo systemctl enable --now dion-zabbix-bot
sudo systemctl status dion-zabbix-bot


дебаг ошибок journalctl -u dion-zabbix-bot -f 


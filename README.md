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
BOT_PASSWORD=passwoed
BOT_NAME=Zabbix Dion Bot
BIND_HOST=0.0.0.0
BIND_PORT=8080  #( выбираем любой порт )
DEFAULT_PARSE_MODE=Markdown
STATE_FILE=/opt/dion-zabbix-bot/state.json


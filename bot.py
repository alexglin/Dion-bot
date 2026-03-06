import json
import os
import threading
import time
import traceback
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv()

BOT_EMAIL = os.getenv("BOT_EMAIL", "")
BOT_PASSWORD = os.getenv("BOT_PASSWORD", "")
BOT_NAME = os.getenv("BOT_NAME", "Zabbix Dion Bot")
BIND_HOST = os.getenv("BIND_HOST", "0.0.0.0")
BIND_PORT = int(os.getenv("BIND_PORT", "8085"))
STATE_FILE = os.getenv("STATE_FILE", "/opt/dion-zabbix-bot/state.json")

BASE_URL = "https://bots-api.dion.vc"
TOKEN_URL = f"{BASE_URL}/platform/v1/token"
GET_ME_URL = f"{BASE_URL}/chats/v2/getMe"
SETTINGS_URL = f"{BASE_URL}/chats/v2/setMySettings"
SET_COMMANDS_URL = f"{BASE_URL}/chats/v2/setMyCommands"
SEND_MESSAGE_URL = f"{BASE_URL}/chats/v2/sendMessage"
GET_UPDATES_URL = f"{BASE_URL}/chats/v2/getUpdates"

TOKEN_TTL_SECONDS = 11 * 60 * 60

app = Flask(__name__)


class DionBot:
    def __init__(self) -> None:
        self.email = BOT_EMAIL
        self.password = BOT_PASSWORD
        self.token: Optional[str] = None
        self.token_received_at: float = 0
        self.lock = threading.Lock()

        self.state: Dict[str, Any] = {
            "offset": None,
            "known_chats": {}
        }
        self._load_state()

    def _load_state(self) -> None:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
                print(f"[state] loaded from {STATE_FILE}", flush=True)
            except Exception as e:
                print(f"[state] failed to load state: {e}", flush=True)

    def _save_state(self) -> None:
        try:
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            tmp = f"{STATE_FILE}.tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
            os.replace(tmp, STATE_FILE)
        except Exception as e:
            print(f"[state] failed to save state: {e}", flush=True)

    def get_token(self) -> str:
        with self.lock:
            now = time.time()
            if self.token and (now - self.token_received_at < TOKEN_TTL_SECONDS):
                return self.token

            print("[auth] requesting new token", flush=True)

            resp = requests.post(
                TOKEN_URL,
                json={
                    "email": self.email,
                    "password": self.password
                },
                timeout=30
            )

            print(f"[auth] token response status={resp.status_code}", flush=True)
            print(f"[auth] token response body={resp.text}", flush=True)

            resp.raise_for_status()
            data = resp.json()

            access_token = data.get("access_token")
            if not access_token:
                raise RuntimeError(f"access_token not found in response: {data}")

            self.token = access_token
            self.token_received_at = now

            print("[auth] token updated successfully", flush=True)
            return self.token

    def _headers(self) -> Dict[str, str]:
        token = self.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def get_me(self) -> Dict[str, Any]:
        resp = requests.get(GET_ME_URL, headers=self._headers(), timeout=30)
        print(f"[getMe] status={resp.status_code} body={resp.text}", flush=True)
        resp.raise_for_status()
        return resp.json()

    def set_my_settings(
        self,
        can_send_dm: bool = True,
        can_join_groups: bool = True,
        can_join_channels: bool = False
    ) -> Dict[str, Any]:
        payload = {
            "can_send_dm": can_send_dm,
            "can_join_groups": can_join_groups,
            "can_join_channels": can_join_channels
        }

        resp = requests.post(
            SETTINGS_URL,
            headers=self._headers(),
            json=payload,
            timeout=30
        )
        print(f"[setMySettings] status={resp.status_code} body={resp.text}", flush=True)
        resp.raise_for_status()
        return resp.json()

    def set_my_commands(self) -> Dict[str, Any]:
        payload = {
            "commands": [
                {"command": "/start", "description": "Зарегистрировать чат для алертов"},
                {"command": "/ping", "description": "Проверка работы бота"},
                {"command": "/chatid", "description": "Показать chat_id текущего чата"}
            ]
        }

        resp = requests.post(
            SET_COMMANDS_URL,
            headers=self._headers(),
            json=payload,
            timeout=30
        )
        print(f"[setMyCommands] status={resp.status_code} body={resp.text}", flush=True)
        resp.raise_for_status()
        return resp.json()

    def send_message(self, chat_id: str, text: str, parse_mode: str = "") -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text[:4096]
        }

        if parse_mode:
            payload["parse_mode"] = parse_mode

        print(f"[sendMessage] payload={json.dumps(payload, ensure_ascii=False)}", flush=True)

        resp = requests.post(
            SEND_MESSAGE_URL,
            headers=self._headers(),
            json=payload,
            timeout=30
        )

        print(f"[sendMessage] status={resp.status_code}", flush=True)
        print(f"[sendMessage] response={resp.text}", flush=True)

        resp.raise_for_status()
        return resp.json()

    def get_updates(self, timeout: int = 30, limit: int = 100) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {
            "timeout": timeout,
            "limit": limit,
            "allowed_updates": ["message", "edited_message", "my_chat_member"]
        }

        if self.state.get("offset") is not None:
            params["offset"] = self.state["offset"]

        resp = requests.get(
            GET_UPDATES_URL,
            headers={"Authorization": f"Bearer {self.get_token()}"},
            params=params,
            timeout=timeout + 10
        )

        print(f"[getUpdates] status={resp.status_code}", flush=True)
        print(f"[getUpdates] response={resp.text}", flush=True)

        resp.raise_for_status()
        data = resp.json()

        if not data.get("ok"):
            return []

        return data.get("result", [])

    def remember_chat(self, chat: Dict[str, Any]) -> None:
        chat_id = chat.get("id")
        if not chat_id:
            return

        self.state["known_chats"][chat_id] = {
            "id": chat_id,
            "name": chat.get("name", ""),
            "type": chat.get("type", ""),
            "updated_at": int(time.time())
        }
        self._save_state()
        print(f"[chat] remembered chat_id={chat_id}", flush=True)

    def process_update(self, upd: Dict[str, Any]) -> None:
        update_id = upd.get("update_id")
        if update_id is not None:
            self.state["offset"] = update_id + 1

        msg = upd.get("message")
        if msg:
            chat = msg.get("chat", {})
            text = (msg.get("text") or "").strip()
            chat_id = chat.get("id")

            self.remember_chat(chat)

            print(f"[update] message chat_id={chat_id} text={text}", flush=True)

            if text == "/start":
                reply = (
                    f"{BOT_NAME} подключён.\n\n"
                    f"Этот чат зарегистрирован для алертов Zabbix.\n"
                    f"chat_id: {chat_id}"
                )
                self.send_message(chat_id, reply)

            elif text == "/ping":
                self.send_message(chat_id, "pong")

            elif text == "/chatid":
                self.send_message(chat_id, str(chat_id))

        my_chat_member = upd.get("my_chat_member")
        if my_chat_member:
            chat = my_chat_member.get("chat", {})
            self.remember_chat(chat)
            print(f"[update] my_chat_member chat={chat}", flush=True)

        self._save_state()

    def polling_loop(self) -> None:
        print("[polling] started", flush=True)

        while True:
            try:
                updates = self.get_updates(timeout=30, limit=100)
                for upd in updates:
                    self.process_update(upd)
            except Exception as e:
                print(f"[polling] error: {e}", flush=True)
                traceback.print_exc()
                time.sleep(5)

    def known_chats(self) -> Dict[str, Any]:
        return self.state.get("known_chats", {})


bot = DionBot()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/debug/chats", methods=["GET"])
def debug_chats():
    return jsonify(bot.known_chats()), 200


@app.route("/zabbix", methods=["POST"])
def zabbix_webhook():
    raw_body = request.data.decode("utf-8", errors="ignore")
    print(f"[zabbix] raw request={raw_body}", flush=True)

    data = request.get_json(silent=True) or {}
    print(f"[zabbix] parsed json={data}", flush=True)

    chat_id = str(data.get("chat_id", "")).strip()
    if not chat_id:
        return jsonify({"ok": False, "error": "chat_id is required"}), 400

    subject = str(data.get("subject", "Zabbix alert")).strip()
    message = str(data.get("message", "")).strip()
    severity = str(data.get("severity", "")).strip()
    host = str(data.get("host", "")).strip()
    event_id = str(data.get("event_id", "")).strip()

    parts: List[str] = []

    if subject:
        parts.append(subject)
    if severity:
        parts.append(f"Severity: {severity}")
    if host:
        parts.append(f"Host: {host}")
    if event_id:
        parts.append(f"Event ID: {event_id}")
    if message:
        parts.append("")
        parts.append(message)

    text = "\n".join(parts).strip()[:4096]

    print(f"[zabbix] final text={text}", flush=True)

    try:
        result = bot.send_message(chat_id, text)
        print(f"[zabbix] send result={result}", flush=True)
        return jsonify({"ok": True, "result": result}), 200
    except Exception as e:
        print(f"[zabbix] ERROR: {e}", flush=True)
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


def bootstrap() -> None:
    if not BOT_EMAIL or not BOT_PASSWORD:
        raise RuntimeError("BOT_EMAIL or BOT_PASSWORD is empty in environment")

    print("[init] bootstrap started", flush=True)

    me = bot.get_me()
    print(f"[init] getMe={me}", flush=True)

    settings_result = bot.set_my_settings(
        can_send_dm=True,
        can_join_groups=True,
        can_join_channels=False
    )
    print(f"[init] setMySettings={settings_result}", flush=True)

    commands_result = bot.set_my_commands()
    print(f"[init] setMyCommands={commands_result}", flush=True)

    print("[init] bootstrap completed", flush=True)


if __name__ == "__main__":
    bootstrap()

    polling_thread = threading.Thread(target=bot.polling_loop, daemon=True)
    polling_thread.start()

    print(f"[flask] starting on {BIND_HOST}:{BIND_PORT}", flush=True)
    app.run(host=BIND_HOST, port=BIND_PORT)

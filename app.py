from http.server import BaseHTTPRequestHandler
import json
import os
import requests

# === Настройки ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не задан в переменных окружения")

# 🔴 ЗАМЕНИТЕ ЭТО НА ВАШИ РЕАЛЬНЫЕ ДАННЫЕ (можно обновлять вручную или по крону)
DATA = {
    "KIC001": {"kic": "KIC001", "city": "Аксарка", "city_type": "село", "address": "ул. Центральная, 15", "fio": "Гранкина Елена Михайловна", "phone": "8-909-198-88-42", "email": "grankina@example.com"},
    "KIC002": {"kic": "KIC002", "city": "Краснодар", "city_type": "город", "address": "ул. Ленина, 1", "fio": "Иванов Иван Иванович", "phone": "+7-918-123-45-67", "email": "ivanov@example.com"},
    # Добавьте все КИЦ вручную или загрузите из JSON-файла
}


def send_telegram_message(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"  # ✅ без пробелов!
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[TG ERROR] {e}")
        return False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        msg = f"✅ Бот работает! Загружено КИЦ: {len(DATA)}\nИспользуйте /start в Telegram"
        self.wfile.write(msg.encode('utf-8'))

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            update = json.loads(post_data)

            if 'message' in update and 'text' in update['message']:
                chat_id = update['message']['chat']['id']
                raw_text = update['message']['text'].strip()
                # Нормализуем: убираем пробелы/дефисы, приводим к верхнему регистру
                key = raw_text.upper().replace(' ', '').replace('-', '').replace('_', '')

                if raw_text == '/start':
                    reply = "👋 Привет! Я <b>бот-куратор КИЦ</b>.\nВведите код КИЦ (например: <code>KIC001</code>)"
                    send_telegram_message(chat_id, reply)
                elif key in DATA:
                    r = DATA[key]
                    reply = (
                        f"✅ <b>КИЦ {r['kic']}</b>\n\n"
                        f"🏘 Город: <b>{r['city']}</b> ({r['city_type']})\n"
                        f"📍 Адрес: {r['address']}\n"
                        f"👤 РКИЦ: <b>{r['fio']}</b>\n"
                        f"📞 Телефон: {r['phone']}"
                    )
                    send_telegram_message(chat_id, reply)
                else:
                    reply = f"❌ КИЦ <code>{raw_text}</code> не найден. Всего: {len(DATA)}"
                    send_telegram_message(chat_id, reply)

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))

        except Exception as e:
            print(f"[ERROR] {e}")
            self.send_response(500)
            self.end_headers()


handler = Handler

from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import re

BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Тестовые данные (временно)
DATA = {
    "KIC001": {"kic": "KIC001", "city": "Аксарка", "address": "ул. Центральная, 15", "fio": "Гранкина Елена Михайловна", "phone": "8-909-198-88-42"},
    "KIC002": {"kic": "KIC002", "city": "Краснодар", "address": "ул. Ленина, 1", "fio": "Иванов Иван Иванович", "phone": "+7-918-123-45-67"},
}

def send_telegram_message(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
        return True
    except:
        return False

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"✅ Бот работает!")
    
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            update = json.loads(post_data)

            if 'message' in update and 'text' in update['message']:
                chat_id = update['message']['chat']['id']
                text = update['message']['text'].strip()
                
                if text == '/start':
                    reply = "👋 Привет! Введите код КИЦ"
                else:
                    key = re.sub(r'[^\w]', '', text.upper())
                    if key in DATA:
                        entry = DATA[key]
                        reply = f"✅ <b>{entry['kic']}</b>\n\n{entry['city']}\n{entry['address']}\n{entry['fio']}\n{entry['phone']}"
                    else:
                        reply = f"❌ КИЦ '{text}' не найден"
                
                send_telegram_message(chat_id, reply)
            
            self.send_response(200)
            self.end_headers()
            
        except Exception as e:
            print(f"Ошибка: {e}")
            self.send_response(500)
            self.end_headers()

handler = Handler

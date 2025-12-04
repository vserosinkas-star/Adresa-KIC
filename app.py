from http.server import BaseHTTPRequestHandler
import json
import os
import requests

BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Mock данные
MOCK_DATA = {
    "KIC001": {
        "kic": "KIC001", "city": "Аксарка", "city_type": "село", 
        "address": "ул. Центральная, 15", "fio": "Гранкина Елена Михайловна",
        "phone": "8-909-198-88-42", "email": "grankina@example.com"
    }
}

def send_telegram_message(chat_id, text):
    if not BOT_TOKEN:
        return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except:
        return False

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
    self.send_response(200)
    self.send_header('Content-type', 'text/plain; charset=utf-8')
    self.end_headers()
    self.wfile.write("✅ Бот куратор КИЦ работает! Используйте /start в Telegram".encode('utf-8'))
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            update = json.loads(post_data)
            
            if 'message' in update:
                chat_id = update['message']['chat']['id']
                text = update['message'].get('text', '').strip()
                
                if text == '/start':
                    response_text = "👋 Привет! Я бот-куратор КИЦ. Введите код КИЦ (например: KIC001)"
                    send_telegram_message(chat_id, response_text)
                elif text.upper() in MOCK_DATA:
                    record = MOCK_DATA[text.upper()]
                    response_text = f"✅ КИЦ {record['kic']}\nГород: {record['city']}\nАдрес: {record['address']}\nРКИЦ: {record['fio']}\nТелефон: {record['phone']}"
                    send_telegram_message(chat_id, response_text)
                else:
                    response_text = f"❌ КИЦ '{text}' не найден. Попробуйте KIC001"
                    send_telegram_message(chat_id, response_text)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

# Vercel требует эту переменную
handler = Handler

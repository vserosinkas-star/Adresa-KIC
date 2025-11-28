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
    },
    "KIC002": {
        "kic": "KIC002", "city": "Белоярск", "city_type": "город",
        "address": "ул. Ленина, 25", "fio": "Гранкина Елена Михайловна", 
        "phone": "8-909-198-88-42", "email": "grankina@example.com"
    }
}

def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "🏢 Поиск по КИЦ"}, {"text": "🏙️ Поиск по городу"}],
            [{"text": "📍 Популярные города"}, {"text": "📊 Статистика"}],
            [{"text": "❓ Помощь"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def send_telegram_message(chat_id, text, reply_markup=None):
    if not BOT_TOKEN:
        print(f"Без BOT_TOKEN: {text}")
        return False
        
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        
        if reply_markup:
            payload["reply_markup"] = reply_markup

        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return False

def process_telegram_update(update):
    if 'message' not in update:
        return {"status": "no message"}
    
    chat_id = update['message']['chat']['id']
    text = update['message'].get('text', '').strip()
    
    if text == '/start':
        response_text = "👋 Привет! Я бот-куратор КИЦ. Выберите тип поиска:"
        keyboard = get_main_keyboard()
        send_telegram_message(chat_id, response_text, keyboard)
        return {"status": "started"}
    
    elif text == "🏢 Поиск по КИЦ":
        response_text = "🔍 Введите код КИЦ (например: KIC001):"
        send_telegram_message(chat_id, response_text)
        return {"status": "waiting_for_kic"}
    
    elif text == "❓ Помощь":
        response_text = (
            "🤖 Помощь по боту-куратору КИЦ\n\n"
            "• Поиск по КИЦ - найти по коду клиентского центра\n"
            "• Поиск по городу - найти все КИЦ в населенном пункте\n"
            "• Статистика - информация о базе данных"
        )
        keyboard = get_main_keyboard()
        send_telegram_message(chat_id, response_text, keyboard)
        return {"status": "help"}
    
    elif text == "📊 Статистика":
        stats_text = f"📊 Статистика:\n• Всего КИЦ: {len(MOCK_DATA)}"
        keyboard = get_main_keyboard()
        send_telegram_message(chat_id, stats_text, keyboard)
        return {"status": "stats"}
    
    elif text.upper() in MOCK_DATA:
        record = MOCK_DATA[text.upper()]
        response_text = (
            f"✅ КИЦ {record['kic']}\n\n"
            f"🏙️ Населенный пункт: {record['city']}\n"
            f"📍 Адрес: {record['address']}\n"
            f"👤 РКИЦ: {record['fio']}\n"
            f"📞 Телефон: {record['phone']}\n"
            f"📧 Email: {record['email']}"
        )
        keyboard = get_main_keyboard()
        send_telegram_message(chat_id, response_text, keyboard)
        return {"status": "kic_found"}
    
    else:
        response_text = f"❌ Не найдено КИЦ по запросу «{text}»."
        keyboard = get_main_keyboard()
        send_telegram_message(chat_id, response_text, keyboard)
        return {"status": "not_found"}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        response_text = "✅ Бот куратор КИЦ работает! Используйте /start в Telegram"
        self.wfile.write(response_text.encode())
        return

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            update = json.loads(post_data)
            result = process_telegram_update(update)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_response = {"error": str(e)}
            self.wfile.write(json.dumps(error_response).encode())

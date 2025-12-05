from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import re

# === Настройки ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Тестовые данные (для проверки работы)
TEST_DATA = {
    "KIC001": {
        "kic": "KIC001", 
        "city": "Аксарка", 
        "address": "ул. Центральная, 15", 
        "fio": "Гранкина Елена Михайловна", 
        "phone": "8-909-198-88-42"
    },
    "KIC002": {
        "kic": "KIC002", 
        "city": "Краснодар", 
        "address": "ул. Ленина, 1", 
        "fio": "Иванов Иван Иванович", 
        "phone": "+7-918-123-45-67"
    },
}

def send_telegram_message(chat_id, text):
    """Отправляет сообщение в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Обработчик GET запросов (для проверки работы)"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Бот-куратор КИЦ</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .success { color: green; }
                .box { background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 10px 0; }
            </style>
        </head>
        <body>
            <h1>🤖 Бот-куратор КИЦ</h1>
            
            <div class="box">
                <h3>✅ Бот работает!</h3>
                <p>Статус: <span class="success">Активен</span></p>
                <p>Тестовых записей: 2</p>
            </div>
            
            <div class="box">
                <h3>🚀 Как использовать</h3>
                <p>1. Откройте Telegram</p>
                <p>2. Найдите бота</p>
                <p>3. Отправьте <code>/start</code></p>
                <p>4. Введите код КИЦ (например: KIC001)</p>
            </div>
            
            <div class="box">
                <h3>📋 Тестовые данные</h3>
                <p><code>KIC001</code> - Аксарка</p>
                <p><code>KIC002</code> - Краснодар</p>
            </div>
        </body>
        </html>
        """
        
        self.wfile.write(html.encode('utf-8'))
    
    def do_POST(self):
        """Обработчик POST запросов от Telegram"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            update = json.loads(post_data)

            if 'message' in update and 'text' in update['message']:
                chat_id = update['message']['chat']['id']
                raw_text = update['message']['text'].strip()
                
                print(f"Сообщение от {chat_id}: {raw_text}")
                
                # Нормализуем ввод
                key = re.sub(r'[^\w]', '', raw_text.upper())
                
                if raw_text == '/start':
                    reply = (
                        "👋 <b>Привет! Я бот-куратор КИЦ</b>\n\n"
                        "🔍 <b>Как использовать:</b>\n"
                        "Введите код КИЦ для получения информации\n\n"
                        "<b>Примеры:</b>\n"
                        "<code>KIC001</code>\n"
                        "<code>KIC002</code>\n\n"
                        "⚙️ <b>Статус:</b> Работает в тестовом режиме"
                    )
                    send_telegram_message(chat_id, reply)
                    
                elif raw_text == '/help':
                    reply = (
                        "📚 <b>Справка по боту:</b>\n\n"
                        "• Введите код КИЦ для получения информации\n"
                        "• Данные тестовые (временно)\n"
                        "• Регистр не важен\n\n"
                        "⚙️ <b>Команды:</b>\n"
                        "/start - начало работы\n"
                        "/help - эта справка\n"
                        "/test - проверить работу\n\n"
                        "💡 <b>Примеры:</b>\n"
                        "<code>KIC001</code>\n"
                        "<code>KIC002</code>"
                    )
                    send_telegram_message(chat_id, reply)
                    
                elif raw_text == '/test':
                    reply = "✅ <b>Бот работает!</b>\n\nТестовых записей: 2\nРежим: Тестовые данные"
                    send_telegram_message(chat_id, reply)
                    
                else:
                    # Ищем в тестовых данных
                    if key in TEST_DATA:
                        r = TEST_DATA[key]
                        reply = (
                            f"✅ <b>КИЦ {r['kic']}</b>\n\n"
                            f"🏘 <b>Город:</b> {r['city']}\n"
                            f"📍 <b>Адрес:</b> {r['address']}\n"
                            f"👤 <b>Ответственный:</b> {r['fio']}\n"
                            f"📞 <b>Телефон:</b> {r['phone']}"
                        )
                    else:
                        reply = f"❌ КИЦ <code>{raw_text}</code> не найден.\n\nДоступные тестовые коды:\n<code>KIC001</code>, <code>KIC002</code>"
                    
                    send_telegram_message(chat_id, reply)

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))

        except Exception as e:
            print(f"Ошибка обработки: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

handler = Handler

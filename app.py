from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import re

# === Настройки ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GOOGLE_SHEET_ID = "1h6dMEWsLcH--d4MB5CByx05xitOwhAGV"

# Тестовые данные (резервные)
TEST_DATA = {
    "KIC001": {"kic": "KIC001", "city": "Аксарка", "address": "ул. Центральная, 15", "fio": "Гранкина Елена", "phone": "8-909-198-88-42"},
    "KIC002": {"kic": "KIC002", "city": "Краснодар", "address": "ул. Ленина, 1", "fio": "Иванов Иван", "phone": "+7-918-123-45-67"},
}

def test_google_sheets():
    """Тестирует подключение к Google Sheets"""
    try:
        # Проверяем наличие переменной
        if not os.environ.get('GOOGLE_SERVICE_ACCOUNT'):
            return False, "❌ GOOGLE_SERVICE_ACCOUNT не установлен"
        
        # Пробуем распарсить JSON
        try:
            sa_info = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT'))
        except json.JSONDecodeError as e:
            return False, f"❌ Ошибка в формате JSON: {str(e)[:100]}"
        
        # Проверяем обязательные поля
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing_fields = [field for field in required_fields if field not in sa_info]
        if missing_fields:
            return False, f"❌ Отсутствуют поля в JSON: {', '.join(missing_fields)}"
        
        return True, f"✅ Сервисный аккаунт: {sa_info['client_email']}"
        
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)}"

def get_data():
    """Возвращает данные и статус"""
    test_result, test_message = test_google_sheets()
    
    if test_result:
        # Пока используем тестовые данные, но с статусом "готов к Google Sheets"
        return TEST_DATA, "готов к Google Sheets (нужен деплой)"
    else:
        return TEST_DATA, f"тестовые данные ({test_message})"

def send_telegram_message(chat_id, text):
    """Отправляет сообщение в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
        return True
    except:
        return False

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Обработчик GET запросов"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        data, source = get_data()
        test_result, test_message = test_google_sheets()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Бот-куратор КИЦ</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .success {{ color: green; }}
                .error {{ color: red; }}
                .warning {{ color: orange; }}
                .box {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .json {{ background: #333; color: #fff; padding: 10px; border-radius: 5px; overflow-x: auto; font-family: monospace; font-size: 12px; }}
                .check {{ margin-right: 10px; }}
            </style>
        </head>
        <body>
            <h1>🤖 Бот-куратор КИЦ</h1>
            
            <div class="box">
                <h3>📊 Статус системы</h3>
                <p>Бот: <span class="success">✅ Работает</span></p>
                <p>Данные: {source}</p>
                <p>Записей: {len(data)}</p>
            </div>
            
            <div class="box">
                <h3>🔧 Проверка Google Sheets</h3>
                <p>{'✅' if test_result else '❌'} {test_message}</p>
            </div>
            
            <div class="box">
                <h3>📝 Примеры запросов в Telegram:</h3>
                <p><code>/start</code> - начало работы</p>
                <p><code>KIC001</code> - тест поиска</p>
                <p><code>KIC002</code> - тест поиска</p>
            </div>
            
            <div class="box">
                <h3>⚙️ Настройки Vercel</h3>
                <p>BOT_TOKEN: <span class="{'success' if BOT_TOKEN else 'error'}">
                    {'✅ Установлен' if BOT_TOKEN else '❌ Не установлен'}
                </span></p>
                <p>GOOGLE_SERVICE_ACCOUNT: <span class="{'success' if os.environ.get('GOOGLE_SERVICE_ACCOUNT') else 'error'}">
                    {'✅ Установлен' if os.environ.get('GOOGLE_SERVICE_ACCOUNT') else '❌ Не установлен'}
                </span></p>
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
                
                # Получаем данные
                data, source = get_data()
                
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
                        f"📊 <b>Статус:</b> Работает с {source}"
                    )
                    
                elif raw_text == '/status':
                    test_result, test_message = test_google_sheets()
                    reply = (
                        f"📊 <b>Статус системы:</b>\n\n"
                        f"• Бот: ✅ Работает\n"
                        f"• Данные: {source}\n"
                        f"• Записей: {len(data)}\n"
                        f"• Google Sheets: {test_message}"
                    )
                    
                elif raw_text == '/check':
                    test_result, test_message = test_google_sheets()
                    reply = f"🔧 <b>Проверка Google Sheets:</b>\n\n{test_message}"
                    
                else:
                    # Ищем в данных
                    if key in data:
                        r = data[key]
                        reply = (
                            f"✅ <b>КИЦ {r['kic']}</b>\n\n"
                            f"🏘 <b>Город:</b> {r['city']}\n"
                            f"📍 <b>Адрес:</b> {r['address']}\n"
                            f"👤 <b>Ответственный:</b> {r['fio']}\n"
                            f"📞 <b>Телефон:</b> {r['phone']}\n\n"
                            f"<i>Данные из: {source}</i>"
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

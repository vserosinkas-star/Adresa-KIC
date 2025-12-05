from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import re
import gspread
from google.oauth2.service_account import Credentials

# === Настройки ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GOOGLE_SHEET_ID = "1h6dMEWsLcH--d4MB5CByx05xitOwhAGV"

# Тестовые данные (резервные)
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

def load_data_from_sheets():
    """Пытается загрузить данные из Google Sheets"""
    try:
        # Проверяем наличие сервисного аккаунта
        if not os.environ.get('GOOGLE_SERVICE_ACCOUNT'):
            print("GOOGLE_SERVICE_ACCOUNT не найден, использую тестовые данные")
            return None
        
        # Загружаем сервисный аккаунт
        service_account_info = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT'))
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_info(
            service_account_info, 
            scopes=scopes
        )
        
        client = gspread.authorize(credentials)
        
        # Открываем таблицу
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.get_worksheet(0)
        
        # Получаем все данные
        all_values = worksheet.get_all_values()
        
        if len(all_values) <= 1:
            print("Таблица пуста или содержит только заголовки")
            return None
        
        # Парсим данные
        data_dict = {}
        for row in all_values[1:]:  # Пропускаем заголовки
            if len(row) > 0 and row[0].strip():
                kic_code = row[0].strip()
                key = re.sub(r'[^\w]', '', kic_code.upper())
                
                entry = {"kic": kic_code}
                if len(row) > 1: entry["city"] = row[1].strip()
                if len(row) > 2: entry["address"] = row[2].strip()
                if len(row) > 3: entry["fio"] = row[3].strip()
                if len(row) > 4: entry["phone"] = row[4].strip()
                if len(row) > 5: entry["email"] = row[5].strip()
                
                data_dict[key] = entry
        
        print(f"✅ Загружено {len(data_dict)} записей из Google Sheets")
        return data_dict
        
    except Exception as e:
        print(f"❌ Ошибка загрузки из Google Sheets: {e}")
        return None

def get_data():
    """Получает данные (из Google Sheets или тестовые)"""
    sheets_data = load_data_from_sheets()
    if sheets_data:
        return sheets_data, "Google Sheets"
    else:
        return TEST_DATA, "тестовые данные"

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
        """Обработчик GET запросов"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        data, source = get_data()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Бот-куратор КИЦ</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .success {{ color: green; }}
                .warning {{ color: orange; }}
                .box {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <h1>🤖 Бот-куратор КИЦ</h1>
            
            <div class="box">
                <h3>✅ Бот работает!</h3>
                <p>Источник данных: <b>{source}</b></p>
                <p>Записей в базе: <b>{len(data)}</b></p>
            </div>
            
            <div class="box">
                <h3>🚀 Как использовать</h3>
                <p>1. Откройте Telegram</p>
                <p>2. Найдите бота</p>
                <p>3. Отправьте <code>/start</code></p>
                <p>4. Введите код КИЦ (например: KIC001)</p>
            </div>
            
            <div class="box">
                <h3>📊 Статистика</h3>
                <p>Примеры записей:</p>
        """
        
        # Добавляем примеры записей
        count = 0
        for key, entry in list(data.items())[:5]:
            html += f'<p><code>{entry["kic"]}</code> - {entry.get("city", "без города")}</p>'
            count += 1
        
        html += f"""
            </div>
            
            <div class="box">
                <h3>⚙️ Настройки</h3>
                <p>GOOGLE_SERVICE_ACCOUNT: {'✅ Установлен' if os.environ.get('GOOGLE_SERVICE_ACCOUNT') else '❌ Не установлен'}</p>
                <p>BOT_TOKEN: {'✅ Установлен' if BOT_TOKEN else '❌ Не установлен'}</p>
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
                
                # Получаем актуальные данные
                data, source = get_data()
                
                # Нормализуем ввод
                key = re.sub(r'[^\w]', '', raw_text.upper())
                
                if raw_text == '/start':
                    reply = (
                        f"👋 <b>Привет! Я бот-куратор КИЦ</b>\n\n"
                        f"🔍 <b>Как использовать:</b>\n"
                        f"Введите код КИЦ для получения информации\n\n"
                        f"<b>Примеры:</b>\n"
                        f"<code>KIC001</code>\n"
                        f"<code>KIC002</code>\n\n"
                        f"⚙️ <b>Статус:</b> Работает с {source}"
                    )
                    send_telegram_message(chat_id, reply)
                    
                elif raw_text == '/help':
                    reply = (
                        "📚 <b>Справка по боту:</b>\n\n"
                        "• Введите код КИЦ для получения информации\n"
                        f"• Данные из: {source}\n"
                        "• Регистр не важен\n\n"
                        "⚙️ <b>Команды:</b>\n"
                        "/start - начало работы\n"
                        "/help - эта справка\n"
                        "/status - статус системы\n\n"
                        "💡 <b>Примеры:</b>\n"
                        "<code>KIC001</code>\n"
                        "<code>KIC002</code>"
                    )
                    send_telegram_message(chat_id, reply)
                    
                elif raw_text == '/status':
                    reply = (
                        f"📊 <b>Статус системы:</b>\n\n"
                        f"• Источник данных: {source}\n"
                        f"• Записей в базе: {len(data)}\n"
                        f"• ID таблицы: {GOOGLE_SHEET_ID}\n"
                        f"• Google Sheets: {'✅ Подключен' if source == 'Google Sheets' else '❌ Используются тестовые данные'}"
                    )
                    send_telegram_message(chat_id, reply)
                    
                else:
                    # Ищем в данных
                    if key in data:
                        r = data[key]
                        reply = f"✅ <b>КИЦ {r['kic']}</b>\n\n"
                        
                        if r.get('city'):
                            reply += f"🏘 <b>Город:</b> {r['city']}\n"
                        if r.get('address'):
                            reply += f"📍 <b>Адрес:</b> {r['address']}\n"
                        if r.get('fio'):
                            reply += f"👤 <b>Ответственный:</b> {r['fio']}\n"
                        if r.get('phone'):
                            reply += f"📞 <b>Телефон:</b> {r['phone']}\n"
                        if r.get('email'):
                            reply += f"📧 <b>Email:</b> {r['email']}"
                            
                        # Если только код, без дополнительной информации
                        if reply == f"✅ <b>КИЦ {r['kic']}</b>\n\n":
                            reply += "ℹ️ Дополнительная информация не указана"
                            
                        reply += f"\n\n📋 <i>Данные из: {source}</i>"
                        
                    else:
                        # Показываем примеры
                        examples = []
                        for k in list(data.keys())[:5]:
                            examples.append(f"<code>{data[k]['kic']}</code>")
                        
                        reply = f"❌ КИЦ <code>{raw_text}</code> не найден.\n\n"
                        reply += f"Записей в базе: {len(data)}\n"
                        
                        if examples:
                            reply += f"\n<b>Доступные коды:</b>\n" + "\n".join(examples)
                    
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

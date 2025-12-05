from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import time

# === Настройки ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не задан в переменных окружения")

# Конфигурация Google Sheets
SHEET_ID = "1h6dMEWsLcH--d4MB5CByx05xitOwhAGV"
SHEET_GID = "1532223079"

# Кеширование данных (обновляем каждые 5 минут)
DATA_CACHE = {
    "data": {},
    "timestamp": None
}
CACHE_DURATION = 300  # 5 минут в секундах

def get_google_sheets_service():
    """Создает клиент для работы с Google Sheets"""
    try:
        # Получаем данные сервисного аккаунта из переменных окружения
        service_account_info = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT'))
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_info(
            service_account_info, 
            scopes=scopes
        )
        
        return gspread.authorize(credentials)
    except Exception as e:
        print(f"[GSHEETS ERROR] Ошибка авторизации: {e}")
        return None

def load_data_from_sheets(force_update=False):
    """Загружает данные из Google Sheets с кешированием"""
    global DATA_CACHE
    
    # Проверяем, можно ли использовать кеш
    if not force_update and DATA_CACHE["timestamp"]:
        time_diff = datetime.now() - DATA_CACHE["timestamp"]
        if time_diff.total_seconds() < CACHE_DURATION:
            print(f"[CACHE] Используем кешированные данные ({len(DATA_CACHE['data'])} записей)")
            return DATA_CACHE["data"]
    
    print("[SHEETS] Загружаем данные из Google Sheets...")
    
    client = get_google_sheets_service()
    if not client:
        print("[SHEETS ERROR] Не удалось подключиться к Google Sheets")
        return DATA_CACHE["data"] if DATA_CACHE["data"] else {}
    
    try:
        # Открываем таблицу
        spreadsheet = client.open_by_key(SHEET_ID)
        
        # Получаем лист по GID
        worksheet = spreadsheet.get_worksheet_by_id(int(SHEET_GID))
        
        # Получаем все данные
        all_data = worksheet.get_all_records()
        
        # Преобразуем в нужный формат
        data_dict = {}
        for row in all_data:
            # Проверяем обязательные поля
            kic_code = str(row.get('KIC', '')).strip()
            if kic_code:
                # Нормализуем ключ
                key = kic_code.upper().replace(' ', '').replace('-', '').replace('_', '')
                
                data_dict[key] = {
                    "kic": kic_code,
                    "city": row.get('Город', '').strip(),
                    "city_type": row.get('Тип населенного пункта', '').strip(),
                    "address": row.get('Адрес', '').strip(),
                    "fio": row.get('ФИО', '').strip(),
                    "phone": row.get('Телефон', '').strip(),
                    "email": row.get('Email', '').strip()
                }
        
        # Обновляем кеш
        DATA_CACHE = {
            "data": data_dict,
            "timestamp": datetime.now()
        }
        
        print(f"[SHEETS] Данные загружены: {len(data_dict)} записей")
        return data_dict
        
    except Exception as e:
        print(f"[SHEETS ERROR] Ошибка загрузки данных: {e}")
        return DATA_CACHE["data"] if DATA_CACHE["data"] else {}

def send_telegram_message(chat_id, text):
    """Отправляет сообщение в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code != 200:
            print(f"[TG ERROR] Код ошибки: {response.status_code}, текст: {response.text}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"[TG ERROR] {e}")
        return False

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Обработчик GET запросов (для проверки работы)"""
        # Пробуем загрузить данные
        data = load_data_from_sheets()
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        status_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Бот-куратор КИЦ</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                .success {{ color: green; font-weight: bold; }}
                .info {{ color: #555; }}
                .timestamp {{ color: #777; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <h1>🤖 Бот-куратор КИЦ</h1>
            <p class="success">✅ Бот работает!</p>
            <p class="info">Загружено КИЦ: <b>{len(data)}</b></p>
            <p class="timestamp">Последнее обновление: {DATA_CACHE['timestamp'] or 'не обновлялось'}</p>
            <p>Используйте команду <code>/start</code> в Telegram для начала работы.</p>
            <hr>
            <p><a href="/refresh" onclick="event.preventDefault(); fetch('/refresh').then(r => r.text()).then(t => alert(t))">🔄 Обновить данные из Google Sheets</a></p>
        </body>
        </html>
        """
        
        self.wfile.write(status_html.encode('utf-8'))
    
    def do_POST(self):
        """Обработчик POST запросов от Telegram"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            update = json.loads(post_data)

            if 'message' in update and 'text' in update['message']:
                chat_id = update['message']['chat']['id']
                raw_text = update['message']['text'].strip()
                
                # Нормализуем ввод
                key = raw_text.upper().replace(' ', '').replace('-', '').replace('_', '')

                if raw_text == '/start':
                    reply = (
                        "👋 <b>Привет! Я бот-куратор КИЦ</b>\n\n"
                        "Введите код КИЦ для получения информации\n"
                        "Например: <code>KIC001</code>\n\n"
                        "Или используйте команды:\n"
                        "/help - помощь\n"
                        "/refresh - обновить данные\n"
                        "/stats - статистика"
                    )
                    send_telegram_message(chat_id, reply)
                    
                elif raw_text == '/help':
                    reply = (
                        "📚 <b>Справка по боту:</b>\n\n"
                        "• Введите код КИЦ для получения информации\n"
                        "• Пример: <code>KIC001</code>, <code>KIC-002</code>\n"
                        "• Данные загружаются из Google Sheets\n"
                        "• Обновляются автоматически каждые 5 минут\n\n"
                        "Команды:\n"
                        "/start - начало работы\n"
                        "/refresh - принудительное обновление\n"
                        "/stats - статистика базы\n"
                        "/help - эта справка"
                    )
                    send_telegram_message(chat_id, reply)
                    
                elif raw_text == '/stats':
                    data = load_data_from_sheets()
                    reply = (
                        f"📊 <b>Статистика базы КИЦ:</b>\n\n"
                        f"• Всего записей: <b>{len(data)}</b>\n"
                        f"• Последнее обновление: {DATA_CACHE['timestamp'].strftime('%H:%M:%S') if DATA_CACHE['timestamp'] else 'не обновлялось'}\n"
                        f"• Следующее обновление через: {CACHE_DURATION // 60} мин.\n\n"
                        f"Примеры запросов:\n"
                        f"<code>KIC001</code>, <code>kic002</code>"
                    )
                    send_telegram_message(chat_id, reply)
                    
                elif raw_text == '/refresh':
                    reply = "🔄 Обновляю данные из Google Sheets..."
                    send_telegram_message(chat_id, reply)
                    
                    # Принудительно обновляем данные
                    data = load_data_from_sheets(force_update=True)
                    
                    reply = f"✅ Данные обновлены!\nЗагружено записей: {len(data)}"
                    send_telegram_message(chat_id, reply)
                    
                else:
                    # Загружаем данные
                    data = load_data_from_sheets()
                    
                    if key in data:
                        r = data[key]
                        reply = (
                            f"✅ <b>КИЦ {r['kic']}</b>\n\n"
                            f"🏘 <b>Населенный пункт:</b> {r['city']} ({r['city_type']})\n"
                            f"📍 <b>Адрес:</b> {r['address']}\n"
                            f"👤 <b>РКИЦ:</b> {r['fio']}\n"
                            f"📞 <b>Телефон:</b> {r['phone']}\n"
                            f"📧 <b>Email:</b> {r['email'] if r['email'] else 'не указан'}"
                        )
                    else:
                        # Предлагаем похожие варианты
                        suggestions = []
                        if data:
                            for k in data.keys():
                                if key in k or k in key:
                                    suggestions.append(data[k]['kic'])
                                if len(suggestions) >= 3:
                                    break
                        
                        reply = f"❌ КИЦ <code>{raw_text}</code> не найден.\n\n"
                        reply += f"Всего КИЦ в базе: {len(data)}\n"
                        
                        if suggestions:
                            reply += "\nВозможно вы искали:\n"
                            for s in suggestions:
                                reply += f"• <code>{s}</code>\n"
                        else:
                            reply += "\nПроверьте правильность ввода.\nПример: <code>KIC001</code>"
                    
                    send_telegram_message(chat_id, reply)

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))

        except Exception as e:
            print(f"[ERROR] {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

# Для тестирования локально
if __name__ == "__main__":
    from http.server import HTTPServer
    print("Загружаем данные при старте...")
    load_data_from_sheets(force_update=True)
    print("Сервер запускается...")
    server = HTTPServer(('localhost', 8080), Handler)
    server.serve_forever()

handler = Handler

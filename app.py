from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import gspread
from google.oauth2.service_account import Credentials
import re

# === Настройки ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не задан в переменных окружения")

# ID Google таблицы
SHEET_ID = "1h6dMEWsLcH--d4MB5CByx05xitOwhAGV"

# Глобальный кеш данных
DATA_CACHE = {}

def get_google_sheets_service():
    """Создает клиент для работы с Google Sheets"""
    try:
        # Проверяем наличие сервисного аккаунта
        service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT')
        if not service_account_json:
            print("❌ GOOGLE_SERVICE_ACCOUNT не найден в переменных окружения")
            return None
        
        service_account_info = json.loads(service_account_json)
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_info(
            service_account_info, 
            scopes=scopes
        )
        
        client = gspread.authorize(credentials)
        print("✅ Google Sheets клиент создан")
        return client
    except Exception as e:
        print(f"❌ Ошибка создания Google Sheets клиента: {str(e)}")
        return None

def load_data_from_sheets():
    """Загружает данные из Google Sheets"""
    print("🔄 Загружаю данные из Google Sheets...")
    
    try:
        client = get_google_sheets_service()
        if not client:
            print("❌ Не удалось подключиться к Google Sheets")
            return {}
        
        # Открываем таблицу
        print(f"📊 Открываю таблицу с ID: {SHEET_ID}")
        spreadsheet = client.open_by_key(SHEET_ID)
        
        # Получаем первый лист
        worksheet = spreadsheet.get_worksheet(0)
        print(f"📋 Лист: {worksheet.title}")
        
        # Получаем все данные
        all_values = worksheet.get_all_values()
        print(f"📈 Получено строк: {len(all_values)}")
        
        if len(all_values) <= 1:
            print("⚠️ В таблице только заголовки или она пуста")
            return {}
        
        # Определяем заголовки
        headers = [str(h).strip().lower() for h in all_values[0]]
        print(f"📝 Заголовки: {headers}")
        
        # Находим индексы колонок
        col_kic = -1
        col_city = -1
        col_address = -1
        col_fio = -1
        col_phone = -1
        col_email = -1
        
        # Ищем колонки по ключевым словам
        for i, header in enumerate(headers):
            if any(word in header for word in ['код', 'kic', 'кци', 'номер', 'id']):
                col_kic = i
            elif any(word in header for word in ['город', 'city', 'населенный']):
                col_city = i
            elif any(word in header for word in ['адрес', 'address']):
                col_address = i
            elif any(word in header for word in ['фио', 'fio', 'ответственный', 'руководитель']):
                col_fio = i
            elif any(word in header for word in ['телефон', 'phone', 'тел']):
                col_phone = i
            elif any(word in header for word in ['email', 'почта', 'e-mail']):
                col_email = i
        
        print(f"📍 Найдены колонки: KIC={col_kic}, Город={col_city}, ФИО={col_fio}")
        
        if col_kic == -1:
            print("❌ Не найдена колонка с кодом КИЦ!")
            return {}
        
        # Парсим данные
        data_dict = {}
        for row in all_values[1:]:  # Пропускаем заголовки
            try:
                kic_value = row[col_kic] if col_kic < len(row) else ""
                kic_code = str(kic_value).strip()
                
                if not kic_code:
                    continue
                
                # Нормализуем ключ
                key = re.sub(r'[^\w]', '', kic_code.upper())
                
                # Собираем данные
                entry = {
                    "kic": kic_code,
                    "city": row[col_city] if col_city != -1 and col_city < len(row) else "",
                    "address": row[col_address] if col_address != -1 and col_address < len(row) else "",
                    "fio": row[col_fio] if col_fio != -1 and col_fio < len(row) else "",
                    "phone": row[col_phone] if col_phone != -1 and col_phone < len(row) else "",
                    "email": row[col_email] if col_email != -1 and col_email < len(row) else ""
                }
                
                data_dict[key] = entry
                
            except Exception as e:
                print(f"⚠️ Ошибка парсинга строки: {str(e)}")
                continue
        
        print(f"✅ Успешно загружено {len(data_dict)} записей")
        
        # Показываем примеры
        if data_dict:
            sample = list(data_dict.items())[:3]
            print("📋 Примеры загруженных данных:")
            for key, value in sample:
                print(f"  • {value['kic']} - {value.get('city', 'Нет города')}")
        
        # Обновляем кеш
        global DATA_CACHE
        DATA_CACHE = data_dict
        
        return data_dict
        
    except Exception as e:
        print(f"❌ Ошибка загрузки данных: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}

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
        
        if response.status_code != 200:
            print(f"❌ Ошибка отправки в Telegram: {response.status_code}")
            print(f"Ответ: {response.text}")
            return False
            
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки сообщения: {e}")
        return False

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Обработчик GET запросов (для проверки работы)"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        # Пытаемся загрузить данные
        data = load_data_from_sheets()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Бот-куратор КИЦ</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .success {{ color: green; }}
                .error {{ color: red; }}
                .info {{ background: #f0f0f0; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <h1>🤖 Бот-куратор КИЦ</h1>
            
            <div class="info">
                <h3>📊 Статус системы</h3>
                <p>Загружено записей: <b>{len(data)}</b></p>
                <p>Статус: <span class="{'success' if data else 'error'}">
                    {'✅ Работает' if data else '❌ Проблемы с загрузкой'}
                </span></p>
            </div>
            
            <div class="info">
                <h3>🔧 Как использовать</h3>
                <p>1. Откройте Telegram</p>
                <p>2. Найдите бота</p>
                <p>3. Отправьте команду <code>/start</code></p>
                <p>4. Введите код КИЦ (например: KIC-001)</p>
            </div>
            
            <div class="info">
                <h3>📁 Информация о таблице</h3>
                <p>ID таблицы: <code>{SHEET_ID}</code></p>
                <p><a href="https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit" target="_blank">
                    🔗 Открыть таблицу
                </a></p>
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
                
                print(f"📨 Сообщение от {chat_id}: {raw_text}")
                
                # Нормализуем ввод
                key = re.sub(r'[^\w]', '', raw_text.upper())
                
                if raw_text == '/start':
                    reply = (
                        "👋 <b>Привет! Я бот-куратор КИЦ</b>\n\n"
                        "🔍 <b>Как использовать:</b>\n"
                        "Введите код КИЦ для получения информации\n\n"
                        "<b>Примеры:</b>\n"
                        "<code>KIC-001</code>\n"
                        "<code>KIC002</code>\n"
                        "<code>KIC 003</code>\n\n"
                        "📊 <b>Данные</b> загружаются из Google Sheets"
                    )
                    send_telegram_message(chat_id, reply)
                    
                elif raw_text == '/help':
                    reply = (
                        "📚 <b>Справка по боту:</b>\n\n"
                        "• Введите код КИЦ для получения информации\n"
                        "• Данные загружаются из Google Sheets\n"
                        "• Обновляются при каждом запросе\n\n"
                        "⚙️ <b>Команды:</b>\n"
                        "/start - начало работы\n"
                        "/test - проверить подключение\n"
                        "/help - эта справка"
                    )
                    send_telegram_message(chat_id, reply)
                    
                elif raw_text == '/test':
                    reply = "🧪 Проверяю подключение к Google Sheets..."
                    send_telegram_message(chat_id, reply)
                    
                    data = load_data_from_sheets()
                    
                    if data:
                        reply = f"✅ <b>Подключение успешно!</b>\n\nЗагружено записей: <b>{len(data)}</b>"
                    else:
                        reply = (
                            "❌ <b>Не удалось подключиться</b>\n\n"
                            "Возможные причины:\n"
                            "1. Нет доступа к таблице\n"
                            "2. Неверный ID таблицы\n"
                            "3. Проблемы с сервисным аккаунтом\n\n"
                            "Проверьте настройки в Vercel."
                        )
                    
                    send_telegram_message(chat_id, reply)
                    
                else:
                    # Пытаемся загрузить данные
                    data = load_data_from_sheets()
                    
                    if not data:
                        reply = "❌ <b>Нет данных для поиска</b>\n\nПожалуйста, используйте /test для проверки подключения."
                        send_telegram_message(chat_id, reply)
                        return
                    
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
                            
                        if reply == f"✅ <b>КИЦ {r['kic']}</b>\n\n":
                            reply += "ℹ️ Дополнительная информация не указана"
                            
                    else:
                        reply = f"❌ КИЦ <code>{raw_text}</code> не найден.\n\nВсего в базе: {len(data)} записей"
                        
                        # Предлагаем примеры
                        examples = []
                        for k in list(data.keys())[:5]:
                            examples.append(f"<code>{data[k]['kic']}</code>")
                        
                        if examples:
                            reply += f"\n\n<b>Примеры:</b>\n" + "\n".join(examples)
                    
                    send_telegram_message(chat_id, reply)

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))

        except Exception as e:
            print(f"❌ Ошибка обработки запроса: {str(e)}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

handler = Handler

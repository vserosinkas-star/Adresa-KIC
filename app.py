from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import gspread
from google.oauth2.service_account import Credentials
import re

# === Настройки ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GOOGLE_SHEET_ID = "1h6dMEWsLcH--d4MB5CByx05xitOwhAGV"

# Резервные тестовые данные
TEST_DATA = {
    "KIC001": {"kic": "KIC001", "city": "Аксарка", "address": "ул. Центральная, 15", "fio": "Гранкина Елена", "phone": "8-909-198-88-42"},
    "KIC002": {"kic": "KIC002", "city": "Краснодар", "address": "ул. Ленина, 1", "fio": "Иванов Иван", "phone": "+7-918-123-45-67"},
}

def get_google_sheets_client():
    """Создает клиент для Google Sheets"""
    try:
        google_sa = os.environ.get('GOOGLE_SERVICE_ACCOUNT')
        if not google_sa:
            return None, "GOOGLE_SERVICE_ACCOUNT не установлен"
        
        service_account_info = json.loads(google_sa)
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_info(
            service_account_info, 
            scopes=scopes
        )
        
        client = gspread.authorize(credentials)
        return client, "Успешно"
    except json.JSONDecodeError:
        return None, "Неверный формат JSON"
    except Exception as e:
        return None, f"Ошибка: {str(e)}"

def load_data_from_sheets():
    """Загружает данные из Google Sheets"""
    try:
        client, message = get_google_sheets_client()
        if not client:
            return None, f"Не удалось подключиться: {message}"
        
        # Открываем таблицу
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.get_worksheet(0)  # Первый лист
        
        # Читаем все данные
        all_values = worksheet.get_all_values()
        
        if len(all_values) <= 1:
            return None, "Таблица пуста или содержит только заголовки"
        
        # Парсим данные
        data_dict = {}
        headers = [h.strip().lower() for h in all_values[0]]
        
        # Находим индексы колонок
        col_indices = {}
        for i, header in enumerate(headers):
            if 'код' in header or 'kic' in header:
                col_indices['kic'] = i
            elif 'город' in header or 'city' in header:
                col_indices['city'] = i
            elif 'адрес' in header or 'address' in header:
                col_indices['address'] = i
            elif 'фио' in header or 'fio' in header:
                col_indices['fio'] = i
            elif 'телефон' in header or 'phone' in header or 'тел' in header:
                col_indices['phone'] = i
            elif 'email' in header or 'почта' in header:
                col_indices['email'] = i
        
        if 'kic' not in col_indices:
            return None, "Не найдена колонка с кодом КИЦ"
        
        # Обрабатываем строки
        for row in all_values[1:]:
            if col_indices['kic'] < len(row) and row[col_indices['kic']].strip():
                kic_code = row[col_indices['kic']].strip()
                key = re.sub(r'[^\w]', '', kic_code.upper())
                
                entry = {"kic": kic_code}
                for field, idx in col_indices.items():
                    if field != 'kic' and idx < len(row):
                        entry[field] = row[idx].strip()
                
                data_dict[key] = entry
        
        return data_dict, f"Загружено {len(data_dict)} записей"
        
    except gspread.exceptions.SpreadsheetNotFound:
        return None, f"Таблица с ID {GOOGLE_SHEET_ID} не найдена"
    except gspread.exceptions.APIError as e:
        return None, f"Ошибка API Google: {str(e)}"
    except Exception as e:
        return None, f"Ошибка загрузки: {str(e)}"

def get_data():
    """Получает данные (пробует Google Sheets, иначе тестовые)"""
    google_sa = os.environ.get('GOOGLE_SERVICE_ACCOUNT')
    
    if google_sa:
        sheets_data, message = load_data_from_sheets()
        if sheets_data:
            return sheets_data, f"Google Sheets ({message})"
        else:
            return TEST_DATA, f"тестовые данные (Google Sheets: {message})"
    else:
        return TEST_DATA, "тестовые данные (GOOGLE_SERVICE_ACCOUNT не установлен)"

def check_environment():
    """Проверяем переменные окружения"""
    results = []
    
    # Проверка BOT_TOKEN
    if BOT_TOKEN:
        results.append(("✅", "BOT_TOKEN установлен"))
    else:
        results.append(("❌", "BOT_TOKEN не установлен"))
    
    # Проверка GOOGLE_SERVICE_ACCOUNT
    google_sa = os.environ.get('GOOGLE_SERVICE_ACCOUNT')
    if google_sa:
        try:
            sa_info = json.loads(google_sa)
            email = sa_info.get('client_email', 'Неизвестный email')
            results.append(("✅", f"GOOGLE_SERVICE_ACCOUNT: {email}"))
            
            # Проверяем подключение к Sheets
            client, msg = get_google_sheets_client()
            if client:
                results.append(("✅", "Подключение к Google Sheets: OK"))
            else:
                results.append(("❌", f"Google Sheets: {msg}"))
                
        except json.JSONDecodeError:
            results.append(("❌", "GOOGLE_SERVICE_ACCOUNT: Неверный JSON"))
    else:
        results.append(("❌", "GOOGLE_SERVICE_ACCOUNT не установлен"))
    
    return results

def send_telegram_message(chat_id, text):
    """Отправляет сообщение в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
        return True
    except Exception as e:
        print(f"Ошибка Telegram: {e}")
        return False

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Обработчик GET запросов"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        data, source = get_data()
        env_checks = check_environment()
        
        # Создаем HTML
        html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Бот-куратор КИЦ</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }
        .success { color: green; }
        .error { color: red; }
        .warning { color: orange; }
        .box { background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0; }
        code { background: #eee; padding: 2px 5px; border-radius: 3px; }
        .instruction { background: #e8f4fc; border-left: 4px solid #2196F3; padding: 15px; margin: 15px 0; }
        .test-btn { background: #4CAF50; color: white; padding: 10px 15px; border: none; border-radius: 5px; cursor: pointer; }
        .test-btn:hover { background: #45a049; }
    </style>
    <script>
        function testGoogleSheets() {
            document.getElementById('test-result').innerHTML = '🔄 Тестирую...';
            fetch('/test-sheets')
                .then(r => r.text())
                .then(text => {
                    document.getElementById('test-result').innerHTML = text;
                })
                .catch(e => {
                    document.getElementById('test-result').innerHTML = '❌ Ошибка: ' + e;
                });
        }
    </script>
</head>
<body>
    <h1>🤖 Бот-куратор КИЦ</h1>
    
    <div class="box">
        <h3>📊 Статус системы</h3>'''
        
        for icon, message in env_checks:
            html += f'<p>{icon} {message}</p>'
        
        html += f'''
        <p>Источник данных: <b>{source}</b></p>
        <p>Записей в базе: <b>{len(data)}</b></p>
    </div>
    
    <div class="box">
        <h3>🔧 Тест подключения</h3>
        <button class="test-btn" onclick="testGoogleSheets()">Проверить Google Sheets</button>
        <div id="test-result" style="margin-top: 10px;"></div>
    </div>
    
    <div class="box">
        <h3>📝 Примеры запросов в Telegram:</h3>
        <p><code>/start</code> - начало работы</p>
        <p><code>/status</code> - статус системы</p>
        <p><code>/test</code> - тест подключения</p>'''
        
        # Показываем примеры данных
        if data:
            html += '<p><b>Примеры кодов:</b></p>'
            count = 0
            for key, entry in list(data.items())[:5]:
                html += f'<p><code>{entry.get("kic", key)}</code> - {entry.get("city", "")}</p>'
                count += 1
        
        html += '''
    </div>'''
        
        # Если нет GOOGLE_SERVICE_ACCOUNT или есть проблемы
        google_sa = os.environ.get('GOOGLE_SERVICE_ACCOUNT')
        if not google_sa:
            html += '''
    <div class="instruction">
        <h3>📖 Добавьте GOOGLE_SERVICE_ACCOUNT в Vercel</h3>
        <p>1. Скопируйте JSON ключ сервисного аккаунта</p>
        <p>2. В Vercel: Settings → Environment Variables</p>
        <p>3. Добавьте переменную: Name=GOOGLE_SERVICE_ACCOUNT, Value=<em>весь JSON</em></p>
        <p>4. Redeploy проект</p>
    </div>'''
        
        html += '''
</body>
</html>'''
        
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
                        f"📊 <b>Статус:</b> {source}"
                    )
                    
                elif raw_text == '/status':
                    env_checks = check_environment()
                    reply = "📊 <b>Статус системы:</b>\n\n"
                    for icon, message in env_checks:
                        reply += f"{icon} {message}\n"
                    reply += f"\n📁 Источник данных: {source}\n"
                    reply += f"📈 Записей в базе: {len(data)}"
                    
                elif raw_text == '/test':
                    if os.environ.get('GOOGLE_SERVICE_ACCOUNT'):
                        sheets_data, message = load_data_from_sheets()
                        if sheets_data:
                            reply = f"✅ <b>Google Sheets подключен!</b>\n\n{message}"
                        else:
                            reply = f"❌ <b>Проблема с Google Sheets:</b>\n{message}"
                    else:
                        reply = "❌ GOOGLE_SERVICE_ACCOUNT не установлен\n\nДобавьте переменную в Vercel"
                    
                elif raw_text == '/help':
                    reply = (
                        "📚 <b>Справка по боту:</b>\n\n"
                        "• Введите код КИЦ для поиска\n"
                        "• Регистр и пробелы не важны\n\n"
                        "⚙️ <b>Команды:</b>\n"
                        "/start - начало работы\n"
                        "/status - статус системы\n"
                        "/test - тест подключения\n"
                        "/help - эта справка\n\n"
                        "💡 <b>Примеры:</b>\n"
                        "<code>KIC001</code>\n"
                        "<code>KIC 002</code>\n"
                        "<code>kic-001</code>"
                    )
                    
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
                            
                        if reply == f"✅ <b>КИЦ {r['kic']}</b>\n\n":
                            reply += "ℹ️ Дополнительная информация не указана"
                            
                        reply += f"\n\n📋 <i>Данные из: {source}</i>"
                        
                    else:
                        # Показываем доступные коды
                        examples = []
                        for k in list(data.keys())[:5]:
                            examples.append(f"<code>{data[k]['kic']}</code>")
                        
                        reply = f"❌ КИЦ <code>{raw_text}</code> не найден.\n\n"
                        reply += f"Записей в базе: {len(data)}\n"
                        
                        if examples:
                            reply += f"\n<b>Примеры кодов:</b>\n" + "\n".join(examples)
                
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

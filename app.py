import json
import os
import requests
import gspread
from google.oauth2.service_account import Credentials
import re
import base64

# ===== КОНФИГУРАЦИЯ =====
BOT_TOKEN = os.environ.get('BOT_TOKEN')
SHEET_ID = "1h6dMEWsLcH--d4MB5CByx05xitOwhAGV"

# Тестовые данные
TEST_DATA = {
    "НОВЫЙ УРЕНГОЙ": {
        "city": "Новый Уренгой",
        "city_type": "Город",
        "kic": "ДО №8369/018 КИЦ Новоуренгойский",
        "address": "629300, г. Новый Уренгой, мкр. Дружба, 3",
        "fio": "Мохначёв Сергей Вячеславович",
        "phone": "929-252-0303",
        "email": "Mokhnachov.S.V@sberbank.ru"
    },
    "НОЯБРЬСК": {
        "city": "Ноябрьск",
        "city_type": "Город",
        "kic": "ДО №8369/023 КИЦ Ноябрьский",
        "address": "629810, г. Ноябрьск, проспект Мира, 76",
        "fio": "Башкирцев Сергей Николаевич",
        "phone": "912-423-6079",
        "email": "snbashkirtsev@sberbank.ru"
    }
}

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def load_google_sheets():
    """Загружает данные из Google Sheets"""
    try:
        sa_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT')
        if not sa_json:
            return None, "GOOGLE_SERVICE_ACCOUNT не найден"
        
        # Декодируем base64 если нужно
        try:
            sa_json = base64.b64decode(sa_json).decode('utf-8')
        except:
            pass
        
        # Очищаем от невидимых символов
        sa_json = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', sa_json)
        
        # Парсим JSON
        sa_info = json.loads(sa_json)
        
        # Авторизуемся
        creds = Credentials.from_service_account_info(
            sa_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        client = gspread.authorize(creds)
        
        # Открываем таблицу
        sheet = client.open_by_key(SHEET_ID)
        worksheet = sheet.get_worksheet(0)
        all_values = worksheet.get_all_values()
        
        if len(all_values) <= 1:
            return None, "Таблица пуста"
        
        # Определяем индексы колонок
        headers = [h.strip().lower() for h in all_values[0]]
        col_map = {}
        
        for i, header in enumerate(headers):
            if 'населенный пункт' in header or 'город' in header:
                col_map['city'] = i
            elif 'тип' in header:
                col_map['type'] = i
            elif 'киц' in header and 'адрес' not in header:
                col_map['kic'] = i
            elif 'адрес' in header:
                col_map['address'] = i
            elif 'фио' in header:
                col_map['fio'] = i
            elif 'телефон' in header:
                col_map['phone'] = i
            elif 'email' in header:
                col_map['email'] = i
        
        # Обрабатываем данные
        data = {}
        for row in all_values[1:]:
            if not row or len(row) == 0:
                continue
            
            city_col = col_map.get('city', 0)
            if city_col < len(row):
                city_name = row[city_col].strip()
                if city_name:
                    key = city_name.upper().strip()
                    
                    data[key] = {
                        "city": city_name,
                        "city_type": row[col_map.get('type', 0)].strip() if col_map.get('type', 0) < len(row) else "",
                        "kic": row[col_map.get('kic', 0)].strip() if col_map.get('kic', 0) < len(row) else "",
                        "address": row[col_map.get('address', 0)].strip() if col_map.get('address', 0) < len(row) else "",
                        "fio": row[col_map.get('fio', 0)].strip() if col_map.get('fio', 0) < len(row) else "",
                        "phone": row[col_map.get('phone', 0)].strip() if col_map.get('phone', 0) < len(row) else "",
                        "email": row[col_map.get('email', 0)].strip() if col_map.get('email', 0) < len(row) else ""
                    }
        
        return data, f"Загружено {len(data)} записей"
        
    except Exception as e:
        print(f"Google Sheets error: {str(e)}")
        return None, f"Ошибка: {str(e)[:100]}"

def normalize_search(query):
    """Нормализует поисковый запрос"""
    return re.sub(r'[^\w\s-]', '', query.upper()).strip()

def find_city(data, query):
    """Ищет город в данных"""
    norm_query = normalize_search(query)
    
    # Прямое совпадение
    if norm_query in data:
        return data[norm_query]
    
    # Частичное совпадение
    for key, city in data.items():
        if norm_query in key or key in norm_query:
            return city
        
        if city.get('city', '').upper() == norm_query:
            return city
    
    return None

def send_telegram_message(chat_id, text):
    """Отправляет сообщение в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        response = requests.post(url, json=payload, timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram send error: {e}")
        return False

def format_city_response(city, source):
    """Форматирует ответ"""
    response = f"📍 <b>{city['city']}</b>"
    if city.get('city_type'):
        response += f" ({city['city_type']})"
    response += "\n\n"
    
    if city.get('kic'):
        response += f"🏢 <b>КИЦ:</b> {city['kic']}\n"
    if city.get('address'):
        response += f"📌 <b>Адрес:</b> {city['address']}\n"
    if city.get('fio'):
        response += f"👤 <b>Ответственный:</b> {city['fio']}\n"
    if city.get('phone'):
        response += f"📞 <b>Телефон:</b> {city['phone']}\n"
    if city.get('email'):
        response += f"📧 <b>Email:</b> {city['email']}\n"
    
    response += f"\n📋 <i>Данные из: {source}</i>"
    return response

# ===== VERCEL HANDLER =====
def handler(request, context):
    """Основной обработчик для Vercel"""
    
    # Определяем метод запроса
    method = request.get('httpMethod', 'GET')
    
    # GET запрос - показываем статус
    if method == 'GET':
        # Проверяем Google Sheets
        has_google_sa = bool(os.environ.get('GOOGLE_SERVICE_ACCOUNT'))
        sheets_data, sheets_msg = load_google_sheets()
        
        if sheets_data:
            data = sheets_data
            source = f"Google Sheets ({sheets_msg})"
        else:
            data = TEST_DATA
            source = f"тестовые данные (Google Sheets: {sheets_msg})"
        
        # Генерируем HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Бот-куратор КИЦ</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; background: #f8f9fa; }}
        .success {{ color: #28a745; }}
        .error {{ color: #dc3545; }}
        .box {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; }}
        h3 {{ color: #555; margin-top: 0; }}
        code {{ background: #e9ecef; padding: 2px 6px; border-radius: 4px; font-family: monospace; }}
    </style>
</head>
<body>
    <h1>🤖 Бот-куратор КИЦ</h1>
    
    <div class="box">
        <h3>📊 Статус системы</h3>
        <p>GOOGLE_SERVICE_ACCOUNT: <span class="{'success' if has_google_sa else 'error'}">
            {'✔ Установлен' if has_google_sa else '✗ Не установлен'}
        </span></p>
        <p>Google Sheets: <span class="{'success' if sheets_data else 'error'}">
            {'✔ Подключен' if sheets_data else '✗ ' + sheets_msg}
        </span></p>
        <p>Источник данных: <b>{source}</b></p>
        <p>Населенных пунктов в базе: <b>{len(data)}</b></p>
    </div>
    
    <div class="box">
        <h3>🔍 Как искать</h3>
        <p>Введите название населенного пункта в Telegram:</p>
        <p><code>Новый Уренгой</code></p>
        <p><code>Ноябрьск</code></p>
        <p>Или используйте команды:</p>
        <p><code>/start</code> - начало работы</p>
        <p><code>/status</code> - статус системы</p>
        <p><code>/search Город</code> - поиск КИЦ</p>
    </div>
    
    <div class="box">
        <h3>📍 Примеры населенных пунктов</h3>"""
        
        # Показываем примеры
        for key in list(data.keys())[:10]:
            city = data[key]
            html += f'<p><code>{city["city"]}</code> - {city.get("city_type", "").upper()}</p>'
        
        html += """
    </div>
</body>
</html>"""
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html; charset=utf-8'
            },
            'body': html
        }
    
    # POST запрос - Telegram webhook
    elif method == 'POST':
        try:
            body = request.get('body', '{}')
            if not body:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'ok': False, 'error': 'Empty body'})
                }
            
            # Парсим JSON
            if isinstance(body, str):
                update = json.loads(body)
            else:
                update = json.loads(body.decode('utf-8'))
            
            # Проверяем, что это сообщение от Telegram
            if 'message' in update and 'text' in update['message']:
                chat_id = update['message']['chat']['id']
                text = update['message']['text'].strip()
                
                # Загружаем данные
                sheets_data, sheets_msg = load_google_sheets()
                if sheets_data:
                    data = sheets_data
                    source = "Google Sheets"
                else:
                    data = TEST_DATA
                    source = "тестовые данные"
                
                # Обрабатываем команды
                if text.lower() == '/start':
                    response_text = f"""👋 <b>Привет! Я бот-куратор КИЦ</b>

🔍 <b>Как использовать:</b>
Просто введите название населенного пункта

<b>Примеры:</b>
<code>Новый Уренгой</code>
<code>Ноябрьск</code>

📊 <b>Статус:</b> {source}
📍 <b>Населенных пунктов в базе:</b> {len(data)}"""
                
                elif text.lower() == '/status':
                    response_text = f"""📊 <b>Статус системы:</b>

• Google Sheets: {'✔ Подключен' if sheets_data else '✗ ' + sheets_msg}
• Населенных пунктов в базе: {len(data)}
• Источник данных: {source}"""
                
                elif text.lower().startswith('/search'):
                    search_query = text[7:].strip()
                    if search_query:
                        city = find_city(data, search_query)
                        if city:
                            response_text = format_city_response(city, source)
                        else:
                            examples = []
                            for key in list(data.keys())[:5]:
                                examples.append(f"<code>{data[key]['city']}</code>")
                            
                            response_text = f"❌ Населенный пункт <code>{search_query}</code> не найден.\n\nДоступные города:\n"
                            response_text += "\n".join(examples)
                    else:
                        response_text = "❌ Укажите название населенного пункта после /search\n\nПример: <code>/search Новый Уренгой</code>"
                
                else:
                    # Обычный поиск
                    city = find_city(data, text)
                    if city:
                        response_text = format_city_response(city, source)
                    else:
                        examples = []
                        for key in list(data.keys())[:5]:
                            examples.append(f"<code>{data[key]['city']}</code>")
                        
                        response_text = f"❌ Населенный пункт <code>{text}</code> не найден.\n\nДоступные города:\n"
                        response_text += "\n".join(examples)
                        response_text += "\n\nИспользуйте команду <code>/search Город</code> для поиска"
                
                # Отправляем ответ
                send_telegram_message(chat_id, response_text)
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({'ok': True})
            }
            
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'body': json.dumps({'ok': False, 'error': 'Invalid JSON'})
            }
        except Exception as e:
            print(f"Handler error: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({'ok': False, 'error': str(e)})
            }
    
    else:
        return {
            'statusCode': 405,
            'body': json.dumps({'ok': False, 'error': 'Method not allowed'})
        }

# Альтернативное имя функции для совместимости
def app(request, context):
    return handler(request, context)

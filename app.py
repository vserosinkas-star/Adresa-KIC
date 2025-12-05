import json
import os
import requests
import gspread
from google.oauth2.service_account import Credentials
import re
import base64

BOT_TOKEN = os.environ.get('BOT_TOKEN')
SHEET_ID = "1h6dMEWsLcH--d4MB5CByx05xitOwhAGV"

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
    },
}

# ===== УТИЛИТЫ =====
def normalize_text(text):
    """Нормализует текст для поиска"""
    return re.sub(r'[^\w\s-]', '', str(text).upper()).strip()

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
        
        sa_info = json.loads(sa_json)
        
        # Авторизация
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
        
        # Заголовки
        headers = [str(h).strip().lower() for h in all_values[0]]
        
        # Находим индексы колонок
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
            if len(row) == 0:
                continue
                
            city_name = row[col_map.get('city', 0)].strip() if col_map.get('city') < len(row) else ""
            if not city_name:
                continue
            
            key = normalize_text(city_name)
            
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
        print(f"Ошибка Google Sheets: {e}")
        return None, f"Ошибка: {str(e)[:100]}"

def find_city(data, query):
    """Ищет город в данных"""
    query_norm = normalize_text(query)
    
    # Прямой поиск
    if query_norm in data:
        return data[query_norm]
    
    # Поиск по частичному совпадению
    for key, city_data in data.items():
        if query_norm in key or key in query_norm:
            return city_data
    
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
    except:
        return False

# ===== ОСНОВНОЙ КОД =====
def handler(event, context):
    """Основной обработчик для Vercel"""
    
    # Определяем HTTP метод
    method = event.get('httpMethod', 'GET')
    
    # Обрабатываем GET запрос (страница статуса)
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
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .box {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .success {{ color: green; }}
        .error {{ color: red; }}
        code {{ background: #eee; padding: 2px 6px; border-radius: 4px; }}
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
    </div>
    
    <div class="box">
        <h3>📝 Команды Telegram</h3>
        <p><code>/start</code> - начало работы</p>
        <p><code>/status</code> - статус системы</p>
        <p><code>/search Город</code> - поиск КИЦ</p>
    </div>
</body>
</html>"""
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html; charset=utf-8',
            },
            'body': html
        }
    
    # Обрабатываем POST запрос (webhook от Telegram)
    elif method == 'POST':
        try:
            body = event.get('body', '{}')
            if isinstance(body, str):
                update = json.loads(body)
            else:
                update = json.loads(body)
            
            if 'message' in update and 'text' in update['message']:
                chat_id = update['message']['chat']['id']
                text = update['message']['text'].strip()
                
                # Загружаем данные
                sheets_data, sheets_msg = load_google_sheets()
                data = sheets_data if sheets_data else TEST_DATA
                source = "Google Sheets" if sheets_data else "тестовые данные"
                
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
                    has_google_sa = bool(os.environ.get('GOOGLE_SERVICE_ACCOUNT'))
                    
                    response_text = f"""📊 <b>Статус системы:</b>

• Google Sheets: {'✔ Подключен' if sheets_data else '✗ ' + sheets_msg}
• Населенных пунктов в базе: {len(data)}
• Источник данных: {source}"""
                
                elif text.lower().startswith('/search'):
                    query = text[7:].strip()
                    if query:
                        city = find_city(data, query)
                        if city:
                            response_text = f"""📍 <b>{city['city']}</b> ({city.get('city_type', '')})

🏢 <b>КИЦ:</b> {city.get('kic', '')}
📌 <b>Адрес:</b> {city.get('address', '')}
👤 <b>Ответственный:</b> {city.get('fio', '')}
📞 <b>Телефон:</b> {city.get('phone', '')}
📧 <b>Email:</b> {city.get('email', '')}

📋 <i>Данные из: {source}</i>"""
                        else:
                            response_text = f"❌ Город <code>{query}</code> не найден.\n\nДоступные города:\n"
                            for city_name in list(data.keys())[:5]:
                                response_text += f"• <code>{data[city_name]['city']}</code>\n"
                    else:
                        response_text = "❌ Укажите название города после /search\nПример: <code>/search Новый Уренгой</code>"
                
                else:
                    # Обычный поиск
                    city = find_city(data, text)
                    if city:
                        response_text = f"""📍 <b>{city['city']}</b> ({city.get('city_type', '')})

🏢 <b>КИЦ:</b> {city.get('kic', '')}
📌 <b>Адрес:</b> {city.get('address', '')}
👤 <b>Ответственный:</b> {city.get('fio', '')}
📞 <b>Телефон:</b> {city.get('phone', '')}
📧 <b>Email:</b> {city.get('email', '')}

📋 <i>Данные из: {source}</i>"""
                    else:
                        response_text = f"❌ Город <code>{text}</code> не найден.\n\nПопробуйте:\n"
                        for city_name in list(data.keys())[:3]:
                            response_text += f"• <code>{data[city_name]['city']}</code>\n"
                        response_text += "\nИли используйте команду <code>/search Город</code>"
                
                # Отправляем ответ в Telegram
                send_telegram_message(chat_id, response_text)
            
            return {
                'statusCode': 200,
                'body': json.dumps({'ok': True})
            }
            
        except Exception as e:
            print(f"Ошибка обработки: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({'ok': False, 'error': str(e)})
            }
    
    # Неподдерживаемый метод
    else:
        return {
            'statusCode': 405,
            'body': json.dumps({'error': 'Method not allowed'})
        }

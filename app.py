from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import gspread
from google.oauth2.service_account import Credentials
import re
import base64
import traceback

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
    "АНТИПАЮТА": {
        "city": "Антипаюта",
        "city_type": "Село",
        "kic": "КИЦ Антипаютинский",
        "address": "Адрес КИЦ в Антипаюте",
        "fio": "ФИО ответственного",
        "phone": "телефон",
        "email": "email@sberbank.ru"
    },
    "ГАЗ-САЛЕ": {
        "city": "Газ-Сале",
        "city_type": "Село",
        "kic": "КИЦ Газ-Салинский",
        "address": "Адрес КИЦ в Газ-Сале",
        "fio": "ФИО ответственного",
        "phone": "телефон",
        "email": "email@sberbank.ru"
    },
    "ТАЗОВСКИЙ": {
        "city": "Тазовский",
        "city_type": "Поселок",
        "kic": "КИЦ Тазовский",
        "address": "Адрес КИЦ в Тазовском",
        "fio": "ФИО ответственного",
        "phone": "телефон",
        "email": "email@sberbank.ru"
    },
}

def debug_log(message):
    """Логирование для отладки"""
    print(f"DEBUG: {message}")

def load_google_sheets():
    """Загружает данные из Google Sheets"""
    try:
        # Получаем JSON сервисного аккаунта из переменных окружения
        sa_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT')
        
        if not sa_json:
            debug_log("GOOGLE_SERVICE_ACCOUNT не найден в переменных окружения")
            return None, "Переменная GOOGLE_SERVICE_ACCOUNT не установлена"
        
        debug_log(f"Длина GOOGLE_SERVICE_ACCOUNT: {len(sa_json)} символов")
        
        # Пробуем декодировать как base64
        try:
            debug_log("Попытка декодирования base64...")
            sa_json = base64.b64decode(sa_json).decode('utf-8')
            debug_log("Успешно декодирован base64")
        except Exception as e:
            debug_log(f"Не удалось декодировать base64 (используем как есть): {str(e)[:100]}")
        
        # Очищаем от невидимых символов
        sa_json = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', sa_json)
        
        # Проверяем, что это валидный JSON
        debug_log("Парсинг JSON...")
        try:
            sa_info = json.loads(sa_json)
            debug_log("JSON успешно распарсен")
        except json.JSONDecodeError as e:
            debug_log(f"Ошибка JSON: {str(e)}")
            debug_log(f"Первые 200 символов: {sa_json[:200]}")
            return None, f"Неверный формат JSON: {str(e)[:100]}"
        
        # Создаем клиент Google Sheets
        debug_log("Создание клиента Google Sheets...")
        try:
            creds = Credentials.from_service_account_info(
                sa_info,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
            )
            client = gspread.authorize(creds)
        except Exception as e:
            debug_log(f"Ошибка авторизации: {str(e)}")
            return None, f"Ошибка авторизации Google: {str(e)[:100]}"
        
        # Открываем таблицу
        debug_log(f"Открытие таблицы с ID: {SHEET_ID}")
        try:
            sheet = client.open_by_key(SHEET_ID)
        except Exception as e:
            debug_log(f"Ошибка открытия таблицы: {str(e)}")
            return None, f"Не удалось открыть таблицу. Проверьте ID и доступы"
        
        # Получаем первый лист
        debug_log("Получение первого листа...")
        try:
            worksheet = sheet.get_worksheet(0)
        except Exception as e:
            debug_log(f"Ошибка получения листа: {str(e)}")
            return None, f"Не удалось получить лист таблицы"
        
        # Получаем все данные
        debug_log("Получение данных из таблицы...")
        all_values = worksheet.get_all_values()
        
        if len(all_values) <= 1:
            return None, "Таблица пуста или содержит только заголовки"
        
        debug_log(f"Получено строк: {len(all_values)}")
        
        # Получаем заголовки
        headers = [str(h).strip() for h in all_values[0]]
        debug_log(f"Заголовки: {headers}")
        
        # Определяем индексы колонок
        col_index = {}
        for i, header in enumerate(headers):
            header_lower = header.lower()
            if 'населенный пункт' in header_lower or 'город' in header_lower:
                col_index['city'] = i
            elif 'тип населенного пункта' in header_lower or 'тип' in header_lower:
                col_index['city_type'] = i
            elif 'киц' in header_lower and 'адрес' not in header_lower:
                col_index['kic'] = i
            elif 'адрес киц' in header_lower or 'адрес' in header_lower:
                col_index['address'] = i
            elif 'фио ркиц' in header_lower or 'фио' in header_lower:
                col_index['fio'] = i
            elif 'телефон ркиц' in header_lower or 'телефон' in header_lower:
                col_index['phone'] = i
            elif 'email ркиц' in header_lower or 'email' in header_lower:
                col_index['email'] = i
        
        debug_log(f"Индексы колонок: {col_index}")
        
        # Проверяем необходимые колонки
        required_cols = ['city']
        missing_cols = [col for col in required_cols if col not in col_index]
        if missing_cols:
            return None, f"Отсутствуют обязательные колонки: {missing_cols}"
        
        # Обрабатываем данные
        result = {}
        for row_num, row in enumerate(all_values[1:], start=2):
            try:
                # Получаем населенный пункт
                city_value = row[col_index['city']].strip() if col_index['city'] < len(row) else ""
                if not city_value:
                    continue
                
                # Нормализуем ключ для поиска
                key = normalize_city_name(city_value)
                
                # Создаем запись
                entry = {
                    "city": city_value,
                    "city_type": row[col_index.get('city_type', col_index['city'])].strip() 
                               if col_index.get('city_type', col_index['city']) < len(row) else "",
                    "kic": row[col_index.get('kic', col_index['city'])].strip() 
                           if col_index.get('kic', col_index['city']) < len(row) else "",
                    "address": row[col_index.get('address', col_index['city'])].strip() 
                              if col_index.get('address', col_index['city']) < len(row) else "",
                    "fio": row[col_index.get('fio', col_index['city'])].strip() 
                           if col_index.get('fio', col_index['city']) < len(row) else "",
                    "phone": row[col_index.get('phone', col_index['city'])].strip() 
                            if col_index.get('phone', col_index['city']) < len(row) else "",
                    "email": row[col_index.get('email', col_index['city'])].strip() 
                            if col_index.get('email', col_index['city']) < len(row) else ""
                }
                
                result[key] = entry
                    
            except Exception as e:
                debug_log(f"Ошибка обработки строки {row_num}: {e}")
                continue
        
        if not result:
            return None, "Не найдено ни одной записи в таблице"
        
        debug_log(f"Успешно загружено {len(result)} записей")
        return result, f"Успешно загружено {len(result)} населенных пунктов из Google Sheets"
        
    except Exception as e:
        error_trace = traceback.format_exc()
        debug_log(f"Критическая ошибка в load_google_sheets: {str(e)}")
        debug_log(f"Трассировка: {error_trace}")
        return None, f"Ошибка: {str(e)[:200]}"

def normalize_city_name(city_name):
    """Нормализует название населенного пункта для поиска"""
    # Убираем лишние символы, приводим к верхнему регистру
    normalized = re.sub(r'[^\w\s-]', '', str(city_name).upper())
    # Заменяем несколько пробелов на один
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    # Убираем лишние слова
    normalized = re.sub(r'\b(ГОРОД|СЕЛО|ПОСЕЛОК|ДЕРЕВНЯ|ПГТ|СТАНЦИЯ)\b', '', normalized, flags=re.IGNORECASE).strip()
    return normalized

def normalize_search_query(query):
    """Нормализует поисковый запрос"""
    # Убираем лишние символы, приводим к верхнему регистру
    normalized = re.sub(r'[^\w\s-]', '', str(query).upper())
    # Заменяем несколько пробелов на один
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

def find_city(data, query):
    """Ищет населенный пункт в данных"""
    normalized_query = normalize_search_query(query)
    
    if not normalized_query:
        return None
    
    # Прямое совпадение
    if normalized_query in data:
        return data[normalized_query]
    
    # Частичное совпадение
    for city_key, city_data in data.items():
        # Проверяем полное совпадение
        if normalized_query == city_key:
            return city_data
        
        # Проверяем вхождение запроса в название
        if normalized_query in city_key:
            return city_data
        
        # Проверяем вхождение названия в запрос
        if city_key in normalized_query:
            return city_data
        
        # Проверяем русское название (без транслитерации)
        if city_data.get('city', '').upper() == normalized_query:
            return city_data
    
    # Поиск по словам (частичное совпадение слов)
    query_words = set(normalized_query.split())
    for city_key, city_data in data.items():
        city_words = set(city_key.split())
        if query_words and city_words and query_words.intersection(city_words):
            return city_data
    
    return None

def send_message(chat_id, text):
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
        return response.status_code == 200
    except Exception as e:
        debug_log(f"Ошибка отправки в Telegram: {e}")
        return False

def format_city_response(city_data, source):
    """Форматирует ответ с информацией о населенном пункте"""
    reply = f"📍 <b>{city_data['city']}</b>"
    if city_data.get('city_type'):
        reply += f" ({city_data['city_type']})"
    reply += "\n\n"
    
    if city_data.get('kic'):
        reply += f"🏢 <b>КИЦ:</b> {city_data['kic']}\n"
    if city_data.get('address'):
        reply += f"📌 <b>Адрес КИЦ:</b> {city_data['address']}\n"
    if city_data.get('fio'):
        reply += f"👤 <b>Ответственный:</b> {city_data['fio']}\n"
    if city_data.get('phone'):
        phone = city_data['phone']
        reply += f"📞 <b>Телефон:</b> {phone}\n"
    if city_data.get('email'):
        email = city_data['email']
        reply += f"📧 <b>Email:</b> {email}"
    
    reply += f"\n\n📋 <i>Данные из: {source}</i>"
    return reply

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Отключаем стандартное логирование"""
        pass
    
    def do_GET(self):
        """Страница статуса"""
        try:
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            # Проверяем подключение к Google Sheets
            has_google_sa = bool(os.environ.get('GOOGLE_SERVICE_ACCOUNT'))
            sheets_data, sheets_msg = load_google_sheets()
            
            if sheets_data:
                data = sheets_data
                source = f"Google Sheets ({sheets_msg})"
            else:
                data = TEST_DATA
                source = f"тестовые данные (Google Sheets: {sheets_msg})"
            
            # Создаем HTML
            html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Бот-куратор КИЦ</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; background: #f8f9fa; }}
        .success {{ color: #28a745; }}
        .error {{ color: #dc3545; }}
        .warning {{ color: #ffc107; }}
        .box {{ background: white; padding: 20px; border-radius: 8px; margin: 15px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; }}
        h3 {{ color: #555; margin-top: 0; }}
        code {{ background: #e9ecef; padding: 2px 6px; border-radius: 4px; font-family: monospace; }}
        .status-container {{ display: flex; align-items: center; gap: 10px; }}
    </style>
</head>
<body>
    <h1>🤖 Бот-куратор КИЦ</h1>
    
    <div class="box">
        <h3>📊 Статус системы</h3>
        <div class="status-container">
            <span>GOOGLE_SERVICE_ACCOUNT:</span>
            <span class="{'success' if has_google_sa else 'error'}">
                {'✅ Установлен' if has_google_sa else '❌ Не установлен'}
            </span>
        </div>
        <div class="status-container">
            <span>Google Sheets:</span>
            <span class="{'success' if sheets_data else 'error'}">
                {'✅ Подключен' if sheets_data else '❌ ' + sheets_msg}
            </span>
        </div>
        <p><strong>Источник данных:</strong> {source}</p>
        <p><strong>Населенных пунктов в базе:</strong> {len(data)}</p>
    </div>
    
    <div class="box">
        <h3>🔍 Как искать</h3>
        <p>Введите название населенного пункта:</p>
        <p><code>Новый Уренгой</code> - ГОРОД</p>
        <p><code>Антипаюта</code> - СЕЛО</p>
        <p><code>Газ-Сале</code> - СЕЛО</p>
        <p><code>Тазовский</code> - ПОСЕЛОК</p>
    </div>
    
    <div class="box">
        <h3>📝 Примеры запросов в Telegram</h3>
        <p><code>/start</code> - начало работы</p>
        <p><code>/status</code> - статус системы</p>
        <p><code>/search Новый Уренгой</code> - поиск по городу</p>
        <p><code>Антипаюта</code> - прямой поиск</p>
        <p><code>/list</code> - список всех населенных пунктов</p>
    </div>
    
    <div class="box">
        <h3>📍 Примеры населенных пунктов</h3>'''
            
            # Показываем несколько примеров
            examples = list(data.values())[:10]
            for city_info in examples:
                html += f'<p><code>{city_info["city"]}</code> - {city_info.get("city_type", "").upper()}</p>'
            
            html += '''
    </div>
</body>
</html>'''
            
            self.wfile.write(html.encode('utf-8'))
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            error_html = f"<h1>Ошибка</h1><p>{str(e)}</p>"
            self.wfile.write(error_html.encode('utf-8'))
    
    def do_POST(self):
        """Обработчик Telegram"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            update = json.loads(post_data)

            if 'message' in update and 'text' in update['message']:
                chat_id = update['message']['chat']['id']
                raw_text = update['message']['text'].strip()
                
                # Получаем данные
                sheets_data, sheets_msg = load_google_sheets()
                if sheets_data:
                    data = sheets_data
                    source = "Google Sheets"
                else:
                    data = TEST_DATA
                    source = "тестовые данные"
                
                # Обрабатываем команды
                if raw_text.lower() == '/start':
                    reply = (
                        "👋 <b>Привет! Я бот-куратор КИЦ</b>\n\n"
                        "🔍 <b>Как использовать:</b>\n"
                        "Введите название населенного пункта для поиска информации о КИЦ\n\n"
                        "<b>Примеры запросов:</b>\n"
                        "<code>Новый Уренгой</code>\n"
                        "<code>Антипаюта</code>\n"
                        "<code>Тазовский</code>\n\n"
                        f"📊 <b>Статус:</b> {source}\n"
                        f"📍 <b>Населенных пунктов в базе:</b> {len(data)}"
                    )
                
                elif raw_text.lower() == '/status':
                    has_google_sa = bool(os.environ.get('GOOGLE_SERVICE_ACCOUNT'))
                    if sheets_data:
                        gs_status = f"✅ Подключен ({sheets_msg})"
                    else:
                        gs_status = f"❌ {sheets_msg}"
                    
                    reply = (
                        f"📊 <b>Статус системы:</b>\n\n"
                        f"• Google Sheets: {gs_status}\n"
                        f"• Населенных пунктов в базе: {len(data)}\n"
                        f"• Источник данных: {source}\n\n"
                        f"🔍 <b>Примеры запросов:</b>\n"
                        f"<code>Новый Уренгой</code>\n"
                        f"<code>Антипаюта</code>\n"
                        f"<code>Тазовский</code>"
                    )
                
                elif raw_text.lower().startswith('/search'):
                    # Команда поиска /search ГОРОД
                    search_query = raw_text[7:].strip()  # Убираем '/search'
                    if not search_query:
                        reply = "❌ Укажите название населенного пункта после команды /search\n\nПример: <code>/search Новый Уренгой</code>"
                    else:
                        city_data = find_city(data, search_query)
                        if city_data:
                            reply = format_city_response(city_data, source)
                        else:
                            # Показываем доступные населенные пункты
                            examples = []
                            for city_key, city_info in list(data.items())[:8]:
                                examples.append(f"<code>{city_info['city']}</code>")
                            
                            reply = f"❌ Населенный пункт <code>{search_query}</code> не найден.\n\n"
                            reply += f"Всего в базе: {len(data)} населенных пунктов\n"
                            if examples:
                                reply += f"\n<b>Примеры:</b>\n" + "\n".join(examples)
                
                elif raw_text.lower() == '/list':
                    # Показать список всех населенных пунктов
                    if len(data) <= 20:
                        reply = "📍 <b>Все населенные пункты в базе:</b>\n\n"
                        for city_key, city_info in sorted(data.items(), key=lambda x: x[1]['city']):
                            reply += f"• {city_info['city']} ({city_info.get('city_type', '')})\n"
                    else:
                        reply = f"📍 <b>Населенных пунктов в базе:</b> {len(data)}\n\n"
                        reply += "<b>Первые 20 населенных пунктов:</b>\n"
                        for i, (city_key, city_info) in enumerate(sorted(list(data.items())[:20], key=lambda x: x[1]['city'])):
                            reply += f"{i+1}. {city_info['city']} ({city_info.get('city_type', '')})\n"
                        reply += f"\n... и еще {len(data) - 20} населенных пунктов"
                
                else:
                    # Обычный поиск по населенному пункту
                    city_data = find_city(data, raw_text)
                    if city_data:
                        reply = format_city_response(city_data, source)
                    else:
                        # Показываем доступные населенные пункты
                        examples = []
                        for city_key, city_info in list(data.items())[:8]:
                            examples.append(f"<code>{city_info['city']}</code>")
                        
                        reply = f"❌ Населенный пункт <code>{raw_text}</code> не найден.\n\n"
                        reply += f"Всего в базе: {len(data)} населенных пунктов\n"
                        if examples:
                            reply += f"\n<b>Примеры:</b>\n" + "\n".join(examples)
                        reply += "\n💡 <b>Подсказка:</b> Используйте команду <code>/list</code> чтобы увидеть все населенные пункты"
                
                send_message(chat_id, reply)
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
            
        except json.JSONDecodeError as e:
            debug_log(f"Ошибка JSON: {e}")
            self.send_response(400)
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": "Invalid JSON"}).encode())
        except Exception as e:
            debug_log(f"Ошибка обработки запроса: {e}")
            debug_log(f"Трассировка: {traceback.format_exc()}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

# Для Vercel
def handler(req, context):
    """Обработчик для Vercel"""
    return Handler()

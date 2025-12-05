from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re
import sys

# === Настройки ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не задан в переменных окружения")

# ID Google таблицы (взять из URL)
SHEET_ID = os.environ.get('GOOGLE_SHEET_ID', "1h6dMEWsLcH--d4MB5CByx05xitOwhAGV")

# Кеширование данных
DATA_CACHE = {
    "data": {},
    "timestamp": None
}

def get_google_sheets_service():
    """Создает клиент для работы с Google Sheets"""
    try:
        # Способ 1: Из переменной окружения (для Vercel)
        if 'GOOGLE_SERVICE_ACCOUNT' in os.environ:
            service_account_info = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT'))
        # Способ 2: Из файла (для локальной разработки)
        elif os.path.exists('service_account.json'):
            with open('service_account.json', 'r') as f:
                service_account_info = json.load(f)
        else:
            print("[ERROR] Не найден сервисный аккаунт Google")
            return None
        
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
        print(f"[GSHEETS ERROR] Ошибка авторизации: {str(e)}")
        return None

def normalize_kic_code(kic_code):
    """Нормализует код КИЦ для поиска"""
    if not kic_code:
        return ""
    # Убираем пробелы, дефисы, приводим к верхнему регистру
    return re.sub(r'[^\w]', '', str(kic_code).upper())

def load_data_from_sheets(force_update=False):
    """Загружает данные из Google Sheets"""
    global SHEET_ID
    print(f"[SHEETS] Начинаю загрузку данных из таблицы {SHEET_ID}...")
    
    client = get_google_sheets_service()
    if not client:
        print("[SHEETS ERROR] Не удалось подключиться к Google Sheets")
        return {}
    
    try:
        # Открываем таблицу
        print(f"[SHEETS] Открываю таблицу ID: {SHEET_ID}")
        spreadsheet = client.open_by_key(SHEET_ID)
        
        # Получаем ПЕРВЫЙ лист
        worksheet = spreadsheet.get_worksheet(0)
        print(f"[SHEETS] Использую первый лист: {worksheet.title}")
        
        # Получаем ВСЕ данные из листа
        print("[SHEETS] Читаю данные...")
        all_values = worksheet.get_all_values()
        
        if not all_values:
            print("[SHEETS ERROR] Лист пустой")
            return {}
        
        print(f"[SHEETS] Получено строк: {len(all_values)}")
        print(f"[SHEETS] Первая строка (заголовки): {all_values[0]}")
        
        # Если в таблице меньше 2 строк (только заголовки)
        if len(all_values) < 2:
            print("[SHEETS WARNING] В таблице только заголовки, данных нет")
            return {}
        
        # Определяем заголовки (первая строка)
        headers = [str(h).strip() for h in all_values[0]]
        
        # Ищем индексы нужных колонок
        column_indexes = {}
        
        # Проходим по всем заголовкам и ищем нужные
        for i, header in enumerate(headers):
            header_lower = header.lower()
            
            # Код КИЦ
            if any(word in header_lower for word in ['код', 'kic', 'кци', 'номер', 'id']):
                if 'kic' not in column_indexes:
                    column_indexes['kic'] = i
                    print(f"[SHEETS] Колонка КИЦ: '{header}' (индекс {i})")
            
            # Город
            if any(word in header_lower for word in ['город', 'city', 'населенный']):
                if 'city' not in column_indexes:
                    column_indexes['city'] = i
                    print(f"[SHEETS] Колонка Город: '{header}' (индекс {i})")
            
            # Адрес
            if any(word in header_lower for word in ['адрес', 'address']):
                if 'address' not in column_indexes:
                    column_indexes['address'] = i
                    print(f"[SHEETS] Колонка Адрес: '{header}' (индекс {i})")
            
            # ФИО
            if any(word in header_lower for word in ['фио', 'fio', 'ответственный', 'руководитель', 'куратор', 'сотрудник']):
                if 'fio' not in column_indexes:
                    column_indexes['fio'] = i
                    print(f"[SHEETS] Колонка ФИО: '{header}' (индекс {i})")
            
            # Телефон
            if any(word in header_lower for word in ['телефон', 'phone', 'тел', 'контакт']):
                if 'phone' not in column_indexes:
                    column_indexes['phone'] = i
                    print(f"[SHEETS] Колонка Телефон: '{header}' (индекс {i})")
            
            # Email
            if any(word in header_lower for word in ['email', 'почта', 'электронная', 'e-mail']):
                if 'email' not in column_indexes:
                    column_indexes['email'] = i
                    print(f"[SHEETS] Колонка Email: '{header}' (индекс {i})")
        
        # КРИТИЧНО: должна быть колонка с кодом КИЦ
        if 'kic' not in column_indexes:
            print("[SHEETS ERROR] Не найдена колонка с кодом КИЦ!")
            print("[SHEETS] Заголовки таблицы:", headers)
            print("[SHEETS] Пожалуйста, убедитесь что есть колонка с названием 'Код', 'KIC', 'КЦИ' и т.д.")
            return {}
        
        # Парсим данные строк
        data_dict = {}
        valid_rows = 0
        
        for row_idx, row in enumerate(all_values[1:], start=2):  # Пропускаем заголовки
            # Пропускаем пустые строки
            if not any(cell.strip() for cell in row):
                continue
            
            try:
                # Берем код КИЦ из соответствующей колонки
                kic_value = row[column_indexes['kic']] if column_indexes['kic'] < len(row) else ""
                kic_code = str(kic_value).strip()
                
                if not kic_code:
                    continue
                
                # Нормализуем ключ
                key = normalize_kic_code(kic_code)
                
                # Собираем данные из всех доступных колонок
                entry = {"kic": kic_code}
                
                # Добавляем город если есть
                if 'city' in column_indexes and column_indexes['city'] < len(row):
                    entry["city"] = row[column_indexes['city']].strip()
                
                # Добавляем адрес если есть
                if 'address' in column_indexes and column_indexes['address'] < len(row):
                    entry["address"] = row[column_indexes['address']].strip()
                
                # Добавляем ФИО если есть
                if 'fio' in column_indexes and column_indexes['fio'] < len(row):
                    entry["fio"] = row[column_indexes['fio']].strip()
                
                # Добавляем телефон если есть
                if 'phone' in column_indexes and column_indexes['phone'] < len(row):
                    entry["phone"] = row[column_indexes['phone']].strip()
                
                # Добавляем email если есть
                if 'email' in column_indexes and column_indexes['email'] < len(row):
                    entry["email"] = row[column_indexes['email']].strip()
                
                # Сохраняем запись
                data_dict[key] = entry
                valid_rows += 1
                
            except Exception as e:
                print(f"[SHEETS WARNING] Ошибка в строке {row_idx}: {str(e)}")
                continue
        
        # Обновляем кеш
        DATA_CACHE["data"] = data_dict
        DATA_CACHE["timestamp"] = datetime.now()
        
        print(f"[SHEETS] Успешно загружено: {valid_rows} записей")
        print(f"[SHEETS] Общее количество записей в кеше: {len(data_dict)}")
        
        # Логируем несколько записей для проверки
        if data_dict:
            print("[SHEETS] Примеры загруженных данных:")
            for i, (key, value) in enumerate(list(data_dict.items())[:3]):
                print(f"  {i+1}. {value.get('kic', key)} - {value.get('city', 'Нет города')} - {value.get('fio', 'Нет ФИО')[:20]}...")
        else:
            print("[SHEETS WARNING] Не загружено ни одной записи!")
        
        return data_dict
        
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"[SHEETS ERROR] Таблица с ID {SHEET_ID} не найдена!")
        print("[SHEETS] Проверьте ID таблицы и права доступа")
        return {}
    except Exception as e:
        print(f"[SHEETS ERROR] Критическая ошибка: {str(e)}")
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
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code != 200:
            print(f"[TG ERROR] Код ошибки: {response.status_code}")
            print(f"[TG ERROR] Ответ: {response.text}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"[TG ERROR] {e}")
        return False

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Обработчик GET запросов (для проверки работы)"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        # Загружаем данные для отображения статуса
        data = load_data_from_sheets()
        
        # Форматируем время обновления
        if DATA_CACHE['timestamp']:
            time_str = DATA_CACHE['timestamp'].strftime('%d.%m.%Y %H:%M:%S')
        else:
            time_str = "никогда"
        
        # Создаем простой список примеров кодов
        examples = []
        if data:
            for i, (key, value) in enumerate(list(data.items())[:5]):
                examples.append(f"<code>{value.get('kic', key)}</code>")
        
        status_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Бот-куратор КИЦ</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
                .success {{ color: green; font-weight: bold; }}
                .error {{ color: red; }}
                .info {{ color: #555; }}
                .box {{ background: #f9f9f9; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                code {{ background: #eee; padding: 2px 5px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <h1>🤖 Бот-куратор КИЦ</h1>
            
            <div class="box">
                <h2>📊 Статус системы</h2>
                <p class="{'success' if data else 'error'}">
                    {'✅ Бот работает' if data else '❌ Проблемы с загрузкой данных'}
                </p>
                <p>Загружено записей: <b>{len(data)}</b></p>
                <p>Последнее обновление: <b>{time_str}</b></p>
            </div>
            
            <div class="box">
                <h2>🔧 Как проверить работу</h2>
                <p>Откройте Telegram и отправьте боту:</p>
                <p><code>/start</code> - для начала работы</p>
                <p>Или введите код КИЦ, например: {', '.join(examples) if examples else '<code>KIC001</code>'}</p>
            </div>
            
            <div class="box">
                <h2>📁 Информация о таблице</h2>
                <p>ID таблицы: <code>{SHEET_ID}</code></p>
                <p><a href="https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit" target="_blank">
                    🔗 Открыть таблицу в Google Sheets
                </a></p>
            </div>
            
            <hr>
            
            <p><small>Версия: 2.0 | Работает с Google Sheets</small></p>
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
                
                print(f"[BOT] Сообщение от {chat_id}: {raw_text}")
                
                # Нормализуем ввод
                key = normalize_kic_code(raw_text)
                
                if raw_text == '/start':
                    reply = (
                        "👋 <b>Привет! Я бот-куратор КИЦ</b>\n\n"
                        "📌 <b>Как использовать:</b>\n"
                        "Просто введите код КИЦ (например: KIC-001)\n\n"
                        "🔄 <b>Команды:</b>\n"
                        "/help - справка\n"
                        "/refresh - обновить данные\n"
                        "/stats - статистика\n"
                        "/test - проверить подключение\n\n"
                        "📝 <b>Примеры запросов:</b>\n"
                        "<code>KIC-001</code>\n"
                        "<code>KIC002</code>\n"
                        "<code>KIC 003</code>"
                    )
                    send_telegram_message(chat_id, reply)
                    
                elif raw_text == '/help':
                    reply = (
                        "📚 <b>Справка по боту</b>\n\n"
                        "Я помогаю найти информацию о КИЦ (Культурно-информационных центрах).\n\n"
                        "🔍 <b>Как искать:</b>\n"
                        "• Введите код КИЦ\n"
                        "• Можно с пробелами, дефисами или без\n"
                        "• Регистр не важен\n\n"
                        "⚙️ <b>Команды:</b>\n"
                        "/start - начало работы\n"
                        "/refresh - обновить данные из таблицы\n"
                        "/stats - статистика базы\n"
                        "/test - проверить подключение\n"
                        "/help - эта справка\n\n"
                        "📊 <b>Данные</b> загружаются из Google Sheets в реальном времени."
                    )
                    send_telegram_message(chat_id, reply)
                    
                elif raw_text == '/stats':
                    data = load_data_from_sheets()
                    if DATA_CACHE['timestamp']:
                        time_str = DATA_CACHE['timestamp'].strftime('%d.%m.%Y %H:%M')
                    else:
                        time_str = "неизвестно"
                    
                    reply = (
                        f"📊 <b>Статистика базы КИЦ</b>\n\n"
                        f"• Всего записей: <b>{len(data)}</b>\n"
                        f"• Последнее обновление: {time_str}\n"
                        f"• Источник данных: Google Sheets\n\n"
                    )
                    
                    # Добавляем примеры
                    if data:
                        reply += "🔍 <b>Примеры кодов:</b>\n"
                        count = 0
                        for kic_code, info in data.items():
                            if count < 3:
                                reply += f"• <code>{info.get('kic', kic_code)}</code>\n"
                                count += 1
                    
                    send_telegram_message(chat_id, reply)
                    
                elif raw_text == '/refresh':
                    reply = "🔄 Загружаю данные из Google Sheets..."
                    send_telegram_message(chat_id, reply)
                    
                    # Принудительно обновляем данные
                    data = load_data_from_sheets()
                    
                    if data:
                        reply = (
                            f"✅ <b>Данные обновлены!</b>\n\n"
                            f"Загружено записей: <b>{len(data)}</b>\n"
                            f"Время обновления: {DATA_CACHE['timestamp'].strftime('%H:%M:%S') if DATA_CACHE['timestamp'] else 'N/A'}\n\n"
                            f"Теперь можно искать КИЦ по коду."
                        )
                    else:
                        reply = (
                            "❌ <b>Не удалось загрузить данные</b>\n\n"
                            "Возможные причины:\n"
                            "1. Нет доступа к таблице\n"
                            "2. Таблица пустая\n"
                            "3. Нет интернет-соединения\n\n"
                            "Проверьте настройки подключения."
                        )
                    
                    send_telegram_message(chat_id, reply)
                    
                elif raw_text in ['/test', '/test_sheets', '/проверка']:
                    # Тестирование подключения
                    reply = "🧪 Проверяю подключение к Google Sheets..."
                    send_telegram_message(chat_id, reply)
                    
                    data = load_data_from_sheets()
                    
                    if data:
                        # Берем случайный пример
                        import random
                        if data:
                            random_key = random.choice(list(data.keys()))
                            example = data[random_key]
                            
                            reply = (
                                f"✅ <b>Подключение успешно!</b>\n\n"
                                f"📊 Загружено записей: <b>{len(data)}</b>\n"
                                f"⏰ Время обновления: {DATA_CACHE['timestamp'].strftime('%H:%M:%S') if DATA_CACHE['timestamp'] else 'N/A'}\n\n"
                                f"📋 <b>Пример данных:</b>\n"
                                f"Код: <code>{example.get('kic', random_key)}</code>\n"
                                f"Город: {example.get('city', 'не указан')}\n"
                                f"ФИО: {example.get('fio', 'не указан')[:30]}"
                            )
                    else:
                        reply = (
                            "❌ <b>Не удалось подключиться</b>\n\n"
                            "Проверьте:\n"
                            "1. Настройки сервисного аккаунта\n"
                            "2. Доступ к таблице\n"
                            "3. Формат данных в таблице\n\n"
                            "Таблица должна содержать колонку с кодом КИЦ."
                        )
                    
                    send_telegram_message(chat_id, reply)
                    
                else:
                    # Обычный запрос КИЦ
                    data = load_data_from_sheets()
                    
                    if not data:
                        reply = (
                            "❌ <b>База данных пуста</b>\n\n"
                            "Используйте /refresh для загрузки данных\n"
                            "или /test для проверки подключения."
                        )
                        send_telegram_message(chat_id, reply)
                        return
                    
                    if key in data:
                        r = data[key]
                        # Формируем ответ
                        reply_parts = [f"✅ <b>КИЦ {r['kic']}</b>\n"]
                        
                        if r.get('city'):
                            reply_parts.append(f"🏘 <b>Город:</b> {r['city']}")
                        
                        if r.get('address'):
                            reply_parts.append(f"📍 <b>Адрес:</b> {r['address']}")
                        
                        if r.get('fio'):
                            reply_parts.append(f"👤 <b>Ответственный:</b> {r['fio']}")
                        
                        if r.get('phone'):
                            reply_parts.append(f"📞 <b>Телефон:</b> {r['phone']}")
                        
                        if r.get('email'):
                            reply_parts.append(f"📧 <b>Email:</b> {r['email']}")
                        
                        reply = "\n".join(reply_parts)
                        
                        # Если мало данных
                        if len(reply_parts) <= 2:
                            reply += "\n\nℹ️ В таблице недостаточно информации по этому КИЦ"
                    
                    else:
                        # Ищем похожие
                        suggestions = []
                        if data:
                            # Просто берем первые несколько кодов
                            for kic_code, info in data.items():
                                if len(suggestions) < 5:
                                    suggestions.append(info.get('kic', kic_code))
                        
                        reply = f"❌ КИЦ <code>{raw_text}</code> не найден.\n\n"
                        reply += f"Всего в базе: <b>{len(data)}</b> записей\n\n"
                        
                        if suggestions:
                            reply += "<b>Доступные КИЦ:</b>\n"
                            for s in suggestions:
                                reply += f"• <code>{s}</code>\n"
                        
                        reply += "\n💡 <b>Подсказка:</b>\nВведите код без пробелов и дефисов"
                    
                    send_telegram_message(chat_id, reply)

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))

        except Exception as e:
            print(f"[ERROR] Ошибка обработки запроса: {str(e)}")
            import traceback
            traceback.print_exc()
            self.send_response(500)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

# Для тестирования локально (этот блок не выполняется в Vercel)
if __name__ == "__main__":
    from http.server import HTTPServer
    
    print("=" * 50)
    print("🤖 Бот-куратор КИЦ")
    print("=" * 50)
    
    # Проверяем токен
    if not BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не установлен!")
        print("Установите переменную окружения BOT_TOKEN")
        sys.exit(1)
    
    # Проверяем наличие сервисного аккаунта
    if not os.path.exists('service_account.json') and 'GOOGLE_SERVICE_ACCOUNT' not in os.environ:
        print("❌ Ошибка: Сервисный аккаунт Google не найден!")
        print("Создайте файл service_account.json или установите переменную GOOGLE_SERVICE_ACCOUNT")
        sys.exit(1)
    
    # Тестируем подключение
    print("\n🔗 Тестирую подключение к Google Sheets...")
    print(f"📁 ID таблицы: {SHEET_ID}")
    data = load_data_from_sheets()
    
    if data:
        print(f"✅ Успешно! Загружено {len(data)} записей")
        print("\n📋 Примеры данных:")
        for i, (key, value) in enumerate(list(data.items())[:5]):
            print(f"  {i+1}. {value.get('kic', key)} - {value.get('city', 'Нет города')} - {value.get('fio', 'Нет ФИО')[:20]}...")
    else:
        print("❌ Не удалось загрузить данные")
        print("\n🔍 Возможные причины:")
        print("1. Нет доступа к таблице")
        print("2. Таблица пустая")
        print("3. Неверный ID таблицы")
        print("4. Нет колонки с кодом КИЦ")
    
    print(f"\n🌐 Сервер запускается на http://localhost:8080")
    print("📱 Настройте вебхук в Telegram:")
    print(f"   https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url=https://ваш-домен/api")
    print("\n⚡ Для остановки сервера нажмите Ctrl+C")
    
    server = HTTPServer(('localhost', 8080), Handler)
    server.serve_forever()

handler = Handler

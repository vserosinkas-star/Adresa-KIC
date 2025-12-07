import os
import logging
import re
import time
import json
from flask import Flask, request, jsonify
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
BOT_TOKEN = '8043513088:AAE8habdyEK0wlixTE34ISTr35t_mQ9vj2k'  # Ваш токен

# Конфигурация Google Sheets
GOOGLE_SHEET_ID = '1h6dMEWsLcH--d4MB5CByx05xitOwhAGV'
GOOGLE_SHEET_GID = '1532223079'  # ID листа
GOOGLE_SHEETS_API_KEY = os.environ.get('GOOGLE_SHEETS_API_KEY', '')

# Кэширование данных
data_cache = None
cache_timestamp = 0
CACHE_DURATION = 300  # 5 минут

def load_data_from_google_sheets():
    """Загрузка данных из Google Sheets"""
    try:
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{GOOGLE_SHEET_ID}/values/{GOOGLE_SHEET_GID}?key={GOOGLE_SHEETS_API_KEY}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            values = data.get('values', [])
            
            if not values:
                logger.warning("Google Sheets вернула пустые данные")
                return []
            
            # Пропускаем заголовок (если есть)
            start_index = 1 if len(values) > 1 and any(header in values[0][0].lower() 
                                                      for header in ['населен', 'locality', 'пункт']) else 0
            
            records = []
            for row in values[start_index:]:
                if len(row) >= 7:
                    record = {
                        'locality': row[0].strip() if len(row) > 0 else '',
                        'type': row[1].strip() if len(row) > 1 else '',
                        'kic': row[2].strip() if len(row) > 2 else '',
                        'address': row[3].strip() if len(row) > 3 else '',
                        'fio': row[4].strip() if len(row) > 4 else '',
                        'phone': row[5].strip() if len(row) > 5 else '',
                        'email': row[6].strip() if len(row) > 6 else ''
                    }
                    
                    # Проверяем, что запись содержит основные данные
                    if record['locality'] and record['kic']:
                        records.append(record)
            
            logger.info(f"Загружено {len(records)} записей из Google Sheets")
            return records
        else:
            logger.error(f"Ошибка при загрузке данных из Google Sheets: {response.status_code}")
            logger.error(f"Ответ: {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"Исключение при загрузке данных из Google Sheets: {str(e)}")
        return []

def get_backup_data():
    """Резервные данные на случай недоступности Google Sheets"""
    backup_data = """Антипаюта|Село|ДО №8369/018 КИЦ Новоуренгойский|629300, г. Новый Уренгой, мкр. Дружба, 3|Мохначёв Сергей Вячеславович|929-252-0303|Mokhnachov.S.V@sberbank.ru
Газ-Сале|Село|ДО №8369/018 КИЦ Новоуренгойский|629300, г. Новый Уренгой, мкр. Дружба, 3|Мохначёв Сергей Вячеславович|929-252-0303|Mokhnachov.S.V@sberbank.ru
Гыда|Село|ДО №8369/018 КИЦ Новоуренгойский|629300, г. Новый Уренгой, мкр. Дружба, 3|Мохначёв Сергей Вячеславович|929-252-0303|Mokhnachov.S.V@sberbank.ru
Новый Уренгой|Город|ДО №8369/018 КИЦ Новоуренгойский|629300, г. Новый Уренгой, мкр. Дружба, 3|Мохначёв Сергей Вячеславович|929-252-0303|Mokhnachov.S.V@sberbank.ru
Тазовский|Поселок|ДО №8369/018 КИЦ Новоуренгойский|629300, г. Новый Уренгой, мкр. Дружба, 3|Мохначёв Сергей Вячеславович|929-252-0303|Mokhnachov.S.V@sberbank.ru
Когалым|Город|ДО №8369/023 КИЦ Ноябрьский|629810, г. Ноябрьск, проспект Мира, 76|Башкирцев Сергей Николаевич|912-423-6079|snbashkirtsev@sberbank.ru
Ноябрьск|Город|ДО №8369/023 КИЦ Ноябрьский|629810, г. Ноябрьск, проспект Мира, 76|Башкирцев Сергей Николаевич|912-423-6079|snbashkirtsev@sberbank.ru
Челябинск|Город|ДО №8597/0290 КИЦ Челябинск|454091, г. Челябинск, пр.Ленина, 26г|Макаров Вадим Геннадьевич|912-890-7492|vgmakarov@sberbank.ru
Екатеринбург|Город|ДО 9016/0505 КИЦ Екатеринбург|620026, г. Екатеринбург, ул.Куйбышева, д.67|Галкина Наталья Владимировна|919-370-6169|Galkina.N.Vladi@sberbank.ru"""
    
    data = []
    for line in backup_data.strip().split('\n'):
        parts = [part.strip() for part in line.split('|')]
        if len(parts) >= 7:
            data.append({
                'locality': parts[0],
                'type': parts[1],
                'kic': parts[2],
                'address': parts[3],
                'fio': parts[4],
                'phone': parts[5],
                'email': parts[6]
            })
    return data

def get_data():
    """Получение данных с кэшированием и загрузкой из Google Sheets"""
    global data_cache, cache_timestamp
    
    current_time = time.time()
    
    # Если кэш устарел или отсутствует, обновляем
    if data_cache is None or current_time - cache_timestamp > CACHE_DURATION:
        logger.info("Обновление кэша данных...")
        
        # Загружаем данные из Google Sheets
        data = load_data_from_google_sheets()
        
        # Если не удалось загрузить из Google Sheets, используем резервные данные
        if not data:
            logger.warning("Используем резервные данные")
            data = get_backup_data()
        
        # Создаем структуры для быстрого поиска
        locality_map = {}  # Поиск по населенному пункту
        kic_map = {}       # Поиск по КИЦ
        
        for record in data:
            locality_lower = record['locality'].lower()
            locality_map[locality_lower] = record
            
            # Извлекаем код КИЦ
            kic_match = re.search(r'№\s*(\d+/\d+)', record['kic'])
            if kic_match:
                kic_code = kic_match.group(1)
                if kic_code not in kic_map:
                    kic_map[kic_code] = []
                kic_map[kic_code].append(record)
            else:
                # Альтернативный поиск кода КИЦ
                alt_match = re.search(r'(\d+/\d+)', record['kic'])
                if alt_match:
                    kic_code = alt_match.group(1)
                    if kic_code not in kic_map:
                        kic_map[kic_code] = []
                    kic_map[kic_code].append(record)
        
        data_cache = {
            'locality_map': locality_map,
            'kic_map': kic_map,
            'raw_data': data,
            'last_update': current_time,
            'source': 'google_sheets' if data and data != get_backup_data() else 'backup'
        }
        
        cache_timestamp = current_time
        logger.info(f"Данные загружены: {len(data)} записей, {len(locality_map)} населенных пунктов, {len(kic_map)} КИЦ")
        logger.info(f"Источник данных: {data_cache['source']}")
    
    return data_cache['locality_map'], data_cache['kic_map']

def get_main_keyboard():
    """Клавиатура главного меню"""
    return {
        "keyboard": [
            [{"text": "🔍 Поиск по населенному пункту"}, {"text": "🏢 Поиск по КИЦ"}],
            [{"text": "📍 Популярные населенные пункты"}, {"text": "📊 Статистика"}],
            [{"text": "🔄 Обновить данные"}, {"text": "❓ Помощь"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_localities_keyboard():
    """Клавиатура с популярными населенными пунктами"""
    locality_map, _ = get_data()
    
    # Получаем список населенных пунктов
    localities = list(locality_map.keys())[:12]  # Берем первые 12
    
    # Создаем клавиатуру с населенными пунктами (по 2 в ряду)
    keyboard = []
    row = []
    for i, locality in enumerate(localities):
        # Используем оригинальное название (не нижний регистр)
        original_name = locality_map[locality]['locality']
        row.append({"text": original_name})
        if len(row) == 2 or i == len(localities) - 1:
            keyboard.append(row)
            row = []
    
    # Добавляем кнопку "Назад"
    keyboard.append([{"text": "↩️ Назад"}])
    
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

@app.route('/')
def home():
    return "✅ Бот для поиска КИЦ работает! Используйте /start в Telegram"

@app.route('/webhook', methods=['POST', 'GET'])
def webhook():
    logger.info("Webhook called")
    
    if request.method == 'GET':
        return jsonify({"status": "webhook is active"})
    
    try:
        update = request.get_json()
        
        if 'message' in update:
            chat_id = update['message']['chat']['id']
            text = update['message'].get('text', '').strip()
            
            if text == '/start':
                response_text = (
                    "👋 Привет! Я бот для поиска информации о КИЦ.\n\n"
                    "Выберите тип поиска:"
                )
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
            
            elif text == "🔍 Поиск по населенному пункту":
                response_text = "🏘️ Введите название населенного пункта (например: Новый Уренгой):"
                send_telegram_message(chat_id, response_text)
            
            elif text == "🏢 Поиск по КИЦ":
                response_text = "🏢 Введите код КИЦ (например: 8369/018):"
                send_telegram_message(chat_id, response_text)
            
            elif text == "📍 Популярные населенные пункты":
                response_text = "📍 Выберите населенный пункт:"
                keyboard = get_localities_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
            
            elif text == "↩️ Назад":
                response_text = "Главное меню:"
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
            
            elif text == "🔄 Обновить данные":
                global data_cache, cache_timestamp
                data_cache = None
                cache_timestamp = 0
                locality_map, kic_map = get_data()
                source = data_cache['source'] if data_cache and 'source' in data_cache else 'unknown'
                
                if source == 'google_sheets':
                    response_text = f"✅ Данные успешно обновлены из Google Sheets\n\nЗагружено {len(locality_map)} записей."
                else:
                    response_text = f"⚠️ Используются резервные данные\n\nЗагружено {len(locality_map)} записей."
                
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
            
            elif text == "❓ Помощь":
                response_text = (
                    "🤖 Помощь по боту поиска КИЦ\n\n"
                    "• 🔍 Поиск по населенному пункту - найти КИЦ по названию населенного пункта\n"
                    "• 🏢 Поиск по КИЦ - найти по коду клиентско-информационного центра\n"
                    "• 📍 Популярные населенные пункты - быстрый выбор из списка\n"
                    "• 📊 Статистика - информация о базе данных\n"
                    "• 🔄 Обновить данные - обновить данные из Google Sheets\n\n"
                    "Просто введите название населенного пункта или код КИЦ!"
                )
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
            
            elif text == "📊 Статистика":
                locality_map, kic_map = get_data()
                source = data_cache['source'] if data_cache and 'source' in data_cache else 'unknown'
                
                stats_text = (
                    f"📊 Статистика базы данных\n\n"
                    f"• Населенных пунктов: {len(locality_map)}\n"
                    f"• Уникальных КИЦ: {len(kic_map)}\n"
                    f"• Источник: {'Google Sheets' if source == 'google_sheets' else 'Резервные данные'}\n"
                    f"• Обновлено: {time.strftime('%H:%M:%S')}\n\n"
                    f"Примеры населенных пунктов:\n"
                )
                
                # Добавляем несколько примеров
                sample_localities = list(locality_map.keys())[:5]
                for locality in sample_localities:
                    record = locality_map[locality]
                    stats_text += f"• {record['locality']} ({record['type']})\n"
                
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, stats_text, keyboard)
            
            else:
                locality_map, kic_map = get_data()
                
                # Проверяем, является ли ввод кодом КИЦ
                kic_match = re.search(r'(\d+/\d+)', text)
                
                if kic_match:
                    # Поиск по коду КИЦ
                    kic_code = kic_match.group(1)
                    logger.info(f"Поиск КИЦ: {kic_code}")
                    
                    records = kic_map.get(kic_code, [])
                    
                    if records:
                        if len(records) == 1:
                            record = records[0]
                            response_text = format_record(record)
                        else:
                            response_text = f"🔍 Найдено {len(records)} записей для КИЦ {kic_code}:\n\n"
                            for i, record in enumerate(records, 1):
                                response_text += f"{i}. {record['locality']} ({record['type']})\n"
                            response_text += "\n🔍 Уточните поиск, введя полное название населенного пункта."
                    else:
                        response_text = f"❌ КИЦ с кодом {kic_code} не найден."
                    
                    keyboard = get_main_keyboard()
                    send_telegram_message(chat_id, response_text, keyboard)
                
                else:
                    # Поиск по населенному пункту
                    locality_lower = text.lower()
                    logger.info(f"Поиск населенного пункта: {text}")
                    
                    record = locality_map.get(locality_lower)
                    
                    if record:
                        response_text = format_record(record)
                    else:
                        # Попробуем найти частичное совпадение
                        matches = []
                        for loc_key in locality_map.keys():
                            if locality_lower in loc_key or loc_key in locality_lower:
                                matches.append(locality_map[loc_key])
                        
                        if matches:
                            if len(matches) == 1:
                                response_text = format_record(matches[0])
                            else:
                                response_text = f"🔍 Найдено {len(matches)} похожих населенных пунктов:\n\n"
                                for i, match in enumerate(matches[:5], 1):
                                    response_text += f"{i}. {match['locality']} ({match['type']})\n"
                                if len(matches) > 5:
                                    response_text += f"... и еще {len(matches) - 5}"
                                response_text += "\n\n🔍 Введите точное название населенного пункта."
                        else:
                            response_text = (
                                f"❌ Населенный пункт «{text}» не найден.\n\n"
                                "Попробуйте другой населенный пункт или используйте кнопки ниже:"
                            )
                    
                    keyboard = get_main_keyboard()
                    send_telegram_message(chat_id, response_text, keyboard)
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Ошибка в webhook: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

def format_record(record):
    """Форматирование записи для отображения"""
    return (
        f"📍 Населенный пункт: {record['locality']} ({record['type']})\n\n"
        f"🏢 КИЦ: {record['kic']}\n"
        f"📫 Адрес КИЦ: {record['address']}\n\n"
        f"👤 РКИЦ: {record['fio']}\n"
        f"📞 Телефон: {record['phone']}\n"
        f"📧 Email: {record['email']}\n\n"
        f"🔄 Для нового поиска используйте кнопки ниже"
    )

def send_telegram_message(chat_id, text, reply_markup=None):
    """Отправка сообщения в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        response = requests.post(url, json=payload, timeout=10)
        logger.info(f"Telegram API response: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Telegram API error: {response.text}")
            
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return False

@app.route('/debug')
def debug():
    locality_map, kic_map = get_data()
    source = data_cache['source'] if data_cache and 'source' in data_cache else 'unknown'
    
    return jsonify({
        "bot_token_exists": bool(BOT_TOKEN),
        "google_sheets_api_key_exists": bool(GOOGLE_SHEETS_API_KEY),
        "records_count": len(locality_map),
        "kic_count": len(kic_map),
        "cache_age_seconds": int(time.time() - cache_timestamp) if data_cache else None,
        "data_source": source,
        "status": "running"
    })

@app.route('/refresh_cache')
def refresh_cache():
    """Принудительное обновление кэша"""
    global data_cache, cache_timestamp
    data_cache = None
    cache_timestamp = 0
    get_data()
    source = data_cache['source'] if data_cache and 'source' in data_cache else 'unknown'
    
    return jsonify({
        "status": "cache refreshed",
        "data_source": source,
        "timestamp": time.time()
    })

if __name__ == '__main__':
    # Предварительная загрузка данных при запуске
    get_data()
    app.run(host='0.0.0.0', port=3000)

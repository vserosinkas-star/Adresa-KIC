import os
import logging
import re
import time
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8043513088:AAE8habdyEK0wlixTE34ISTr35t_mQ9vj2k')

# URL для публично опубликованной таблицы (замените на ваш после публикации)
PUBLIC_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQH5RckHh9JwG_i0qZ2oBzYbQ3n9N7VZJjZtN3X3JZ8q3jK3JpX0xV8_9VlL4b6kXp4Q1dQY8YjX/pub?gid=1532223079&single=true&output=csv"

# Кэширование данных
data_cache = None
cache_timestamp = 0
CACHE_DURATION = 300  # 5 минут

def get_google_sheet_data():
    """Получение данных из публично опубликованной таблицы"""
    try:
        logger.info(f"Загружаем данные по публичному URL: {PUBLIC_SHEET_URL}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(PUBLIC_SHEET_URL, headers=headers, timeout=15)
        
        if response.status_code == 200:
            text = response.text
            
            if not text.strip():
                logger.warning("Получен пустой ответ")
                return []
            
            # Разделяем строки
            lines = text.strip().split('\n')
            logger.info(f"Получено строк: {len(lines)}")
            
            records = []
            
            for i, line in enumerate(lines):
                # Пропускаем пустые строки
                if not line.strip():
                    continue
                
                # Разделяем по запятой (CSV формат)
                # Учитываем, что значения могут быть в кавычках
                parts = []
                current = ''
                in_quotes = False
                
                for char in line:
                    if char == '"':
                        in_quotes = not in_quotes
                    elif char == ',' and not in_quotes:
                        parts.append(current.strip())
                        current = ''
                    else:
                        current += char
                
                # Добавляем последнюю часть
                parts.append(current.strip())
                
                # Убираем кавычки из значений
                parts = [part.strip('"') for part in parts]
                
                # Если у нас минимум 7 частей
                if len(parts) >= 7:
                    record = {
                        'locality': parts[0],
                        'type': parts[1],
                        'kic': parts[2],
                        'address': parts[3],
                        'fio': parts[4],
                        'phone': parts[5],
                        'email': parts[6]
                    }
                    
                    # Проверяем, что это не заголовок и есть основные данные
                    if i > 0 and record['locality'] and record['kic']:
                        records.append(record)
                        logger.debug(f"Строка {i+1}: {record['locality']} - {record['kic']}")
                elif len(parts) > 0:
                    # Если столбцов меньше, но есть данные
                    logger.warning(f"Строка {i+1}: недостаточно столбцов ({len(parts)})")
            
            if records:
                logger.info(f"Успешно загружено {len(records)} записей")
                return records
            else:
                logger.warning("Не найдено записей в данных")
                return []
        else:
            logger.error(f"Ошибка при загрузке данных: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Исключение при загрузке данных: {str(e)}", exc_info=True)
        return []

def get_backup_data():
    """Резервные данные"""
    backup_data = [
        {
            'locality': 'Антипаюта',
            'type': 'Село',
            'kic': 'ДО №8369/018 КИЦ Новоуренгойский',
            'address': '629300, г. Новый Уренгой, мкр. Дружба, 3',
            'fio': 'Мохначёв Сергей Вячеславович',
            'phone': '929-252-0303',
            'email': 'Mokhnachov.S.V@sberbank.ru'
        },
        {
            'locality': 'Газ-Сале',
            'type': 'Село',
            'kic': 'ДО №8369/018 КИЦ Новоуренгойский',
            'address': '629300, г. Новый Уренгой, мкр. Дружба, 3',
            'fio': 'Мохначёв Сергей Вячеславович',
            'phone': '929-252-0303',
            'email': 'Mokhnachov.S.V@sberbank.ru'
        },
        {
            'locality': 'Гыда',
            'type': 'Село',
            'kic': 'ДО №8369/018 КИЦ Новоуренгойский',
            'address': '629300, г. Новый Уренгой, мкр. Дружба, 3',
            'fio': 'Мохначёв Сергей Вячеславович',
            'phone': '929-252-0303',
            'email': 'Mokhnachov.S.V@sberbank.ru'
        },
        {
            'locality': 'Новый Уренгой',
            'type': 'Город',
            'kic': 'ДО №8369/018 КИЦ Новоуренгойский',
            'address': '629300, г. Новый Уренгой, мкр. Дружба, 3',
            'fio': 'Мохначёв Сергей Вячеславович',
            'phone': '929-252-0303',
            'email': 'Mokhnachov.S.V@sberbank.ru'
        },
        {
            'locality': 'Тазовский',
            'type': 'Поселок',
            'kic': 'ДО №8369/018 КИЦ Новоуренгойский',
            'address': '629300, г. Новый Уренгой, мкр. Дружба, 3',
            'fio': 'Мохначёв Сергей Вячеславович',
            'phone': '929-252-0303',
            'email': 'Mokhnachov.S.V@sberbank.ru'
        },
        {
            'locality': 'Когалым',
            'type': 'Город',
            'kic': 'ДО №8369/023 КИЦ Ноябрьский',
            'address': '629810, г. Ноябрьск, проспект Мира, 76',
            'fio': 'Башкирцев Сергей Николаевич',
            'phone': '912-423-6079',
            'email': 'snbashkirtsev@sberbank.ru'
        },
        {
            'locality': 'Ноябрьск',
            'type': 'Город',
            'kic': 'ДО №8369/023 КИЦ Ноябрьский',
            'address': '629810, г. Ноябрьск, проспект Мира, 76',
            'fio': 'Башкирцев Сергей Николаевич',
            'phone': '912-423-6079',
            'email': 'snbashkirtsev@sberbank.ru'
        },
        {
            'locality': 'Челябинск',
            'type': 'Город',
            'kic': 'ДО №8597/0290 КИЦ Челябинск',
            'address': '454091, г. Челябинск, пр.Ленина, 26г',
            'fio': 'Макаров Вадим Геннадьевич',
            'phone': '912-890-7492',
            'email': 'vgmakarov@sberbank.ru'
        },
        {
            'locality': 'Екатеринбург',
            'type': 'Город',
            'kic': 'ДО 9016/0505 КИЦ Екатеринбург',
            'address': '620026, г. Екатеринбург, ул.Куйбышева, д.67',
            'fio': 'Галкина Наталья Владимировна',
            'phone': '919-370-6169',
            'email': 'Galkina.N.Vladi@sberbank.ru'
        }
    ]
    return backup_data

def get_data():
    """Получение данных с кэшированием"""
    global data_cache, cache_timestamp
    
    current_time = time.time()
    
    if data_cache is None or current_time - cache_timestamp > CACHE_DURATION:
        logger.info("Обновление кэша данных...")
        
        # Пробуем загрузить из Google Sheets
        data = get_google_sheet_data()
        
        # Если не удалось, используем резервные данные
        if not data:
            logger.warning("Используем резервные данные")
            data = get_backup_data()
        
        # Создаем структуры для поиска
        locality_map = {}
        kic_map = {}
        
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
        logger.info(f"Данные загружены: {len(data)} записей")
        logger.info(f"Источник данных: {data_cache['source']}")
    
    return data_cache['locality_map'], data_cache['kic_map']

# ... (остальной код остается таким же, как в предыдущем примере) ...

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
    
    localities = list(locality_map.keys())[:12]
    
    keyboard = []
    row = []
    for i, locality in enumerate(localities):
        original_name = locality_map[locality]['locality']
        row.append({"text": original_name})
        if len(row) == 2 or i == len(localities) - 1:
            keyboard.append(row)
            row = []
    
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
                    kic_code = kic_match.group(1)
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
                    locality_lower = text.lower()
                    record = locality_map.get(locality_lower)
                    
                    if record:
                        response_text = format_record(record)
                    else:
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
        logger.error(f"Ошибка в webhook: {str(e)}")
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
        "public_sheet_url": PUBLIC_SHEET_URL,
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
    return jsonify({"status": "cache refreshed"})

if __name__ == '__main__':
    get_data()
    app.run(host='0.0.0.0', port=3000)

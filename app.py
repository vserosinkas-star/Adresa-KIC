import os
import logging
import re
import time
import csv
import io
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8043513088:AAE8habdyEK0wlixTE34ISTr35t_mQ9vj2k')

# Кэширование данных
data_cache = None
cache_timestamp = 0
CACHE_DURATION = 300  # 5 минут

def try_different_sheet_urls():
    """Пробуем разные URL для доступа к таблице"""
    
    sheet_id = '1h6dMEWsLcH--d4MB5CByx05xitOwhAGV'
    gid = '1532223079'  # ID листа
    
    urls_to_try = [
        # Основной CSV экспорт
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv",
        
        # Публичный доступ
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/pub?gid={gid}&output=csv",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/pub?output=csv",
        
        # Альтернативные форматы
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv",
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/csv,application/csv,*/*'
    }
    
    for url in urls_to_try:
        try:
            logger.info(f"Пробуем URL: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Успешно! Получен ответ с кодом 200 от {url}")
                return response.text
            else:
                logger.warning(f"URL {url} вернул код {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Ошибка при загрузке с {url}: {str(e)}")
    
    return None

def get_google_sheet_data():
    """Получение данных из Google Sheets"""
    try:
        logger.info("Пробуем загрузить данные из Google Sheets...")
        
        # Пробуем разные URL
        csv_data = try_different_sheet_urls()
        
        if not csv_data:
            logger.error("Не удалось загрузить данные ни с одного URL")
            return []
        
        # Парсим CSV
        csv_file = io.StringIO(csv_data)
        
        # Пробуем разные разделители
        for delimiter in [',', ';', '\t', '|']:
            try:
                csv_file.seek(0)
                dialect = csv.Sniffer().sniff(csv_file.read(1024))
                csv_file.seek(0)
                reader = csv.reader(csv_file, dialect)
                break
            except:
                csv_file.seek(0)
                reader = csv.reader(csv_file, delimiter=delimiter)
                try:
                    # Пробуем прочитать первую строку
                    first_row = next(reader)
                    if len(first_row) >= 3:  # Если есть хотя бы 3 столбца
                        csv_file.seek(0)
                        reader = csv.reader(csv_file, delimiter=delimiter)
                        logger.info(f"Используем разделитель: {repr(delimiter)}")
                        break
                except:
                    continue
        
        records = []
        headers = None
        
        for i, row in enumerate(reader):
            # Пропускаем пустые строки
            if not any(cell.strip() for cell in row):
                continue
            
            # Первая непустая строка - заголовок
            if headers is None:
                headers = row
                logger.info(f"Заголовки: {headers}")
                continue
            
            # Нормализуем количество столбцов
            if len(row) < len(headers):
                # Дополняем пустыми значениями
                row = row + [''] * (len(headers) - len(row))
            elif len(row) > len(headers):
                # Обрезаем лишние
                row = row[:len(headers)]
            
            # Ищем нужные столбцы по заголовкам
            record = {}
            
            # Маппим заголовки к нашим полям
            for idx, header in enumerate(headers):
                header_lower = str(header).lower().strip()
                
                if any(keyword in header_lower for keyword in ['насел', 'город', 'мест', 'locality']):
                    record['locality'] = row[idx].strip()
                elif any(keyword in header_lower for keyword in ['тип', 'type', 'вид']):
                    record['type'] = row[idx].strip()
                elif any(keyword in header_lower for keyword in ['киц', 'kic', 'до', 'отдел']):
                    record['kic'] = row[idx].strip()
                elif any(keyword in header_lower for keyword in ['адрес', 'address']):
                    record['address'] = row[idx].strip()
                elif any(keyword in header_lower for keyword in ['фио', 'fio', 'имя', 'ркиц', 'ответств']):
                    record['fio'] = row[idx].strip()
                elif any(keyword in header_lower for keyword in ['тел', 'phone', 'телефон', 'контакт']):
                    record['phone'] = row[idx].strip()
                elif any(keyword in header_lower for keyword in ['email', 'почта', 'емайл']):
                    record['email'] = row[idx].strip()
            
            # Проверяем, что у нас есть необходимые поля
            if not record.get('locality'):
                # Если не нашли по заголовкам, берем по порядку
                if len(row) >= 1:
                    record['locality'] = row[0].strip()
            
            if not record.get('kic'):
                if len(row) >= 3:
                    record['kic'] = row[2].strip()
            
            # Заполняем остальные поля по умолчанию
            record.setdefault('type', row[1].strip() if len(row) > 1 else '')
            record.setdefault('address', row[3].strip() if len(row) > 3 else '')
            record.setdefault('fio', row[4].strip() if len(row) > 4 else '')
            record.setdefault('phone', row[5].strip() if len(row) > 5 else '')
            record.setdefault('email', row[6].strip() if len(row) > 6 else '')
            
            # Проверяем, что запись содержит основные данные
            if record['locality'] and record['kic']:
                records.append(record)
                logger.debug(f"Строка {i+1}: {record['locality']} - {record['kic']}")
        
        if records:
            logger.info(f"Успешно загружено {len(records)} записей из Google Sheets")
            return records
        else:
            logger.warning("Данные загружены, но не удалось найти записи")
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

# Остальная часть кода остается без изменений...

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

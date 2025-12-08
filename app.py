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

# URL для Google Sheets - используем CSV экспорт
GOOGLE_SHEET_ID = '1h6dMEWsLcH--d4MB5CByx05xitOwhAGV'
GOOGLE_SHEET_GID = '1532223079'  # ID листа "Общий"

# Формируем правильный URL для CSV экспорта
PUBLIC_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=csv&gid={GOOGLE_SHEET_GID}"

# Кэширование данных
data_cache = None
cache_timestamp = 0
CACHE_DURATION = 300  # 5 минут

def get_google_sheet_data():
    """Получение данных из Google Sheets через CSV экспорт"""
    try:
        logger.info(f"Загружаем данные по URL: {PUBLIC_SHEET_URL}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(PUBLIC_SHEET_URL, headers=headers, timeout=15)
        
        if response.status_code == 200:
            # Проверяем, что это действительно CSV
            content_type = response.headers.get('Content-Type', '').lower()
            content = response.text[:200]  # Первые 200 символов для проверки
            
            logger.info(f"Content-Type: {content_type}")
            logger.info(f"Первые 200 символов ответа: {content}")
            
            if 'html' in content_type or '<html' in content.lower() or '<!doctype' in content.lower():
                logger.error("Получен HTML вместо CSV. Таблица вероятно требует авторизации.")
                return []
            
            # Пробуем разные кодировки
            encodings = ['utf-8', 'cp1251', 'windows-1251', 'iso-8859-1']
            
            for encoding in encodings:
                try:
                    decoded_text = response.content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                decoded_text = response.text
            
            # Парсим CSV
            try:
                # Используем StringIO для csv.reader
                csv_data = io.StringIO(decoded_text)
                
                # Автоматически определяем разделитель
                sample = csv_data.read(1024)
                csv_data.seek(0)
                
                # Пробуем разные разделители
                for delimiter in [',', ';', '\t']:
                    csv_data.seek(0)
                    try:
                        reader = csv.reader(csv_data, delimiter=delimiter)
                        rows = list(reader)
                        if len(rows) > 1:
                            logger.info(f"Успешно распарсено с разделителем '{delimiter}': {len(rows)} строк")
                            return process_csv_rows(rows)
                    except Exception as e:
                        logger.debug(f"Разделитель '{delimiter}' не подошел: {e}")
                        continue
                
                # Если не получилось, пробуем простой парсинг
                logger.info("Пробуем простой парсинг CSV...")
                return parse_csv_simple(decoded_text)
                
            except Exception as e:
                logger.error(f"Ошибка парсинга CSV: {e}")
                return parse_csv_simple(decoded_text)
                
        else:
            logger.error(f"Ошибка при загрузке данных: {response.status_code}")
            logger.error(f"Ответ: {response.text[:500]}")
            return []
            
    except Exception as e:
        logger.error(f"Исключение при загрузке данных: {str(e)}", exc_info=True)
        return []

def parse_csv_simple(csv_text):
    """Простой парсинг CSV"""
    lines = csv_text.strip().split('\n')
    records = []
    
    for i, line in enumerate(lines):
        # Пропускаем пустые строки
        if not line.strip():
            continue
        
        # Разделяем строку, учитывая кавычки
        parts = []
        current_part = ''
        in_quotes = False
        
        for char in line:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                parts.append(current_part.strip())
                current_part = ''
            else:
                current_part += char
        
        # Добавляем последнюю часть
        parts.append(current_part.strip())
        
        # Убираем кавычки
        parts = [part.strip('"') for part in parts]
        
        # Пропускаем заголовок
        if i == 0 and any(header in ' '.join(parts).lower() for header in ['населен', 'locality', 'город', 'населённый']):
            logger.info(f"Пропускаем заголовок: {parts}")
            continue
        
        # Нужно минимум 3 столбца: населенный пункт, тип, КИЦ
        if len(parts) >= 3:
            record = {
                'locality': parts[0],
                'type': parts[1] if len(parts) > 1 else '',
                'kic': parts[2] if len(parts) > 2 else '',
                'address': parts[3] if len(parts) > 3 else '',
                'fio': parts[4] if len(parts) > 4 else '',
                'phone': parts[5] if len(parts) > 5 else '',
                'email': parts[6] if len(parts) > 6 else ''
            }
            
            # Проверяем, что это реальные данные, а не случайный текст
            if (record['locality'] and len(record['locality']) < 100 and 
                not any(keyword in record['locality'].lower() for keyword in ['function', 'var ', 'return', 'if(', 'for('])):
                
                # Логируем первые несколько записей
                if len(records) < 3:
                    logger.info(f"Найдена запись: {record['locality']}")
                
                records.append(record)
    
    logger.info(f"Простой парсинг нашел {len(records)} записей")
    return records

def process_csv_rows(rows):
    """Обработка строк CSV"""
    records = []
    
    for i, row in enumerate(rows):
        # Пропускаем пустые строки
        if not any(cell.strip() for cell in row):
            continue
        
        # Пропускаем заголовок
        if i == 0 and any(header in ' '.join(row).lower() for header in ['населен', 'locality', 'город', 'населённый']):
            logger.info(f"Заголовок CSV: {row}")
            continue
        
        # Нужно минимум 3 столбца
        if len(row) >= 3:
            record = {
                'locality': row[0].strip(),
                'type': row[1].strip() if len(row) > 1 else '',
                'kic': row[2].strip() if len(row) > 2 else '',
                'address': row[3].strip() if len(row) > 3 else '',
                'fio': row[4].strip() if len(row) > 4 else '',
                'phone': row[5].strip() if len(row) > 5 else '',
                'email': row[6].strip() if len(row) > 6 else ''
            }
            
            # Проверяем, что это реальные данные
            if (record['locality'] and len(record['locality']) < 100 and 
                not any(keyword in record['locality'].lower() for keyword in ['function', 'var ', 'return', 'if(', 'for('])):
                
                # Логируем первые несколько записей
                if len(records) < 3:
                    logger.info(f"Найдена запись (CSV): {record['locality']}")
                
                records.append(record)
    
    logger.info(f"CSV парсинг нашел {len(records)} записей")
    return records

def get_data():
    """Получение данных с кэшированием ТОЛЬКО из Google Sheets"""
    global data_cache, cache_timestamp
    
    current_time = time.time()
    
    if data_cache is None or current_time - cache_timestamp > CACHE_DURATION:
        logger.info("Обновление кэша данных из Google Sheets...")
        
        # Загружаем ТОЛЬКО из Google Sheets
        data = get_google_sheet_data()
        
        # Если не удалось загрузить, используем пустые данные
        if not data:
            logger.error("Не удалось загрузить данные из Google Sheets")
            data = []
        
        # Создаем структуры для поиска
        locality_map = {}
        all_records = []  # Сохраняем все записи для поиска
        kic_map = {}
        
        for record in data:
            # Очищаем и нормализуем данные
            record['locality'] = record['locality'].strip()
            record['type'] = record['type'].strip()
            record['kic'] = record['kic'].strip()
            
            # Проверяем, что это реальный населенный пункт, а не JS код или пустая строка
            if (record['locality'] and len(record['locality']) < 50 and 
                record['locality'].lower() != 'населенный пункт' and
                not any(keyword in record['locality'].lower() for keyword in ['function', 'var ', 'return', 'if(', 'for('])):
                
                locality_lower = record['locality'].lower()
                
                # Для точного поиска сохраняем в словарь
                locality_map[locality_lower] = record
                
                # Сохраняем все записи для поиска по подстроке
                all_records.append(record)
                
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
            'all_records': all_records,  # Сохраняем все записи для поиска
            'kic_map': kic_map,
            'raw_data': data,
            'last_update': current_time,
            'source': 'google_sheets' if data else 'empty'
        }
        
        cache_timestamp = current_time
        logger.info(f"Данные загружены: {len(all_records)} записей, {len(kic_map)} КИЦ")
        logger.info(f"Источник данных: {data_cache['source']}")
        
        # Логируем первые 10 записей для проверки
        if all_records:
            logger.info("Первые 10 записей из таблицы:")
            for i, record in enumerate(all_records[:10]):
                logger.info(f"{i+1}. {record['locality']} ({record['type']}) - {record['kic']}")
    
    return data_cache['locality_map'], data_cache['all_records'], data_cache['kic_map']

def extract_kic_info(kic_text):
    """Извлекает информацию о КИЦ из строки"""
    # Ищем номер ДО
    do_match = re.search(r'ДО\s*№\s*(\d+/\d+)', kic_text)
    do_number = do_match.group(1) if do_match else ""
    
    # Ищем название КИЦ (всё после "КИЦ")
    kic_name_match = re.search(r'КИЦ\s*(.+)', kic_text)
    if kic_name_match:
        kic_name = kic_name_match.group(1).strip()
    else:
        # Если нет "КИЦ", используем всю строку
        kic_name = kic_text.strip()
    
    return do_number, kic_name

def find_all_matches(all_records, search_text):
    """Находит все совпадения по поисковому тексту в Google Sheets"""
    search_lower = search_text.lower()
    matches = []
    
    # Ищем во ВСЕХ записях из Google Sheets
    for record in all_records:
        # Проверяем, содержит ли название населенного пункта искомый текст
        if search_lower in record['locality'].lower():
            # Фильтруем только реальные совпадения
            if (record['locality'] and len(record['locality']) < 50 and 
                not any(keyword in record['locality'].lower() for keyword in ['function', 'var ', 'return', 'if('])):
                matches.append(record)
    
    # Убираем дубликаты (если есть одинаковые записи)
    unique_matches = []
    seen = set()
    
    for match in matches:
        # Создаем уникальный ключ для каждой записи
        key = (match['locality'].lower(), match['type'], match['kic'], match['address'])
        if key not in seen:
            seen.add(key)
            unique_matches.append(match)
    
    return unique_matches

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
    """Клавиатура с популярными населенными пунктами из Google Sheets"""
    locality_map, all_records, _ = get_data()
    
    # Фильтруем только реальные населенные пункты
    real_localities = []
    for locality_key, record in locality_map.items():
        if (record['locality'] and len(record['locality']) < 50 and 
            not any(keyword in record['locality'].lower() for keyword in ['function', 'var ', 'return', 'if('])):
            real_localities.append(record['locality'])
    
    # Убираем дубликаты названий
    unique_localities = []
    seen = set()
    for locality in real_localities:
        if locality not in seen:
            seen.add(locality)
            unique_localities.append(locality)
    
    # Берем первые 12 реальных населенных пунктов
    localities = unique_localities[:12]
    
    keyboard = []
    row = []
    for i, locality in enumerate(localities):
        row.append({"text": locality})
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
                    "👋 Привет! Я бот Адреса КИЦ.\n\n"
                    "Я ищу данные в Google Sheets таблице.\n"
                    "Выберите тип поиска:"
                )
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
            
            elif text == "🔍 Поиск по населенному пункту":
                response_text = "🏘️ Введите название населенного пункта (например: Октябрьское):"
                send_telegram_message(chat_id, response_text)
            
            elif text == "🏢 Поиск по КИЦ":
                response_text = "🏢 Введите код КИЦ (например: 8598/0496):"
                send_telegram_message(chat_id, response_text)
            
            elif text == "📍 Популярные населенные пункты":
                response_text = "📍 Выберите населенный пункт из Google Sheets:"
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
                locality_map, all_records, kic_map = get_data()
                
                if all_records:
                    response_text = f"✅ Данные успешно обновлены из Google Sheets\n\nЗагружено {len(all_records)} записей."
                else:
                    response_text = "❌ Не удалось загрузить данные из Google Sheets. Проверьте доступ к таблице."
                
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
            
            elif text == "❓ Помощь":
                response_text = (
                    "🤖 Помощь по боту поиска КИЦ\n\n"
                    "• 🔍 Поиск по населенному пункту - найти КИЦ по названию населенного пункта\n"
                    "• 🏢 Поиск по КИЦ - найти по коду кассово-инкассаторского центра\n"
                    "• 📍 Популярные населенные пункты - быстрый выбор из списка\n"
                    "• 📊 Статистика - информация о базе данных\n"
                    "• 🔄 Обновить данные - обновить данные из Google Sheets\n\n"
                    "📝 Данные загружаются из Google Sheets таблицы\n"
                    "📊 Формат таблицы: Название | Тип | КИЦ | Адрес | ФИО | Телефон | Email\n\n"
                    "🔍 Примеры поиска:\n"
                    "• При вводе 'Октябрь' найдет все населенные пункты, содержащие это слово\n"
                    "• При вводе '8598/0496' найдет все записи с этим кодом КИЦ\n"
                    "• Можно вводить часть названия: 'окт', 'октя', 'октяб', 'ктя'"
                )
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
            
            elif text == "📊 Статистика":
                locality_map, all_records, kic_map = get_data()
                source = data_cache['source'] if data_cache and 'source' in data_cache else 'unknown'
                
                # Считаем только реальные записи
                real_records = 0
                example_records = []
                
                for record in all_records:
                    if (record['locality'] and len(record['locality']) < 50 and 
                        not any(keyword in record['locality'].lower() for keyword in ['function', 'var ', 'return', 'if('])):
                        real_records += 1
                        if len(example_records) < 5:
                            example_records.append(record)
                
                stats_text = (
                    f"📊 Статистика базы данных из Google Sheets\n\n"
                    f"• Всего записей: {real_records}\n"
                    f"• Уникальных КИЦ: {len(kic_map)}\n"
                    f"• Источник: Google Sheets\n"
                    f"• Обновлено: {time.strftime('%H:%M:%S')}\n"
                    f"• URL таблицы: https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}\n\n"
                )
                
                if example_records:
                    stats_text += "Примеры населенных пунктов:\n"
                    for record in example_records:
                        stats_text += f"• {record['locality']} ({record['type']})\n"
                else:
                    stats_text += "❌ Нет данных. Проверьте доступ к Google Sheets таблице."
                
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, stats_text, keyboard)
            
            else:
                locality_map, all_records, kic_map = get_data()
                
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
                                do_number, kic_name = extract_kic_info(record['kic'])
                                response_text += f"{i}. {record['locality']} ({record['type']})"
                                if do_number:
                                    response_text += f" ДО №{do_number}"
                                if kic_name:
                                    response_text += f" КИЦ {kic_name}"
                                response_text += "\n"
                            response_text += "\n🔍 Уточните поиск, введя полное название населенного пункта."
                    else:
                        response_text = f"❌ КИЦ с кодом {kic_code} не найден в Google Sheets."
                    
                    keyboard = get_main_keyboard()
                    send_telegram_message(chat_id, response_text, keyboard)
                
                else:
                    # Ищем точное совпадение
                    locality_lower = text.lower()
                    record = locality_map.get(locality_lower)
                    
                    if record:
                        response_text = format_record(record)
                    else:
                        # Ищем ВСЕ совпадения (включая частичные) В Google Sheets
                        matches = find_all_matches(all_records, text)
                        
                        if matches:
                            if len(matches) == 1:
                                response_text = format_record(matches[0])
                            else:
                                response_text = f"🔍 Найдено {len(matches)} похожих населенных пунктов в Google Sheets:\n\n"
                                for i, match in enumerate(matches, 1):
                                    do_number, kic_name = extract_kic_info(match['kic'])
                                    response_text += f"{i}. {match['locality']} ({match['type']})"
                                    if do_number:
                                        response_text += f" ДО №{do_number}"
                                    if kic_name:
                                        response_text += f" КИЦ {kic_name}"
                                    response_text += "\n"
                                
                                response_text += "\n🔍 Введите полное и точное название населенного пункта для получения подробной информации."
                        else:
                            # Проверяем, есть ли вообще данные в таблице
                            if not all_records:
                                response_text = (
                                    f"❌ Нет данных в Google Sheets таблице.\n\n"
                                    "Проверьте:\n"
                                    f"1. Доступ к таблице: https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}\n"
                                    "2. Что таблица опубликована для общего доступа\n"
                                    "3. Нажмите '🔄 Обновить данные' для повторной загрузки"
                                )
                            else:
                                response_text = (
                                    f"❌ Населенный пункт «{text}» не найден в Google Sheets.\n\n"
                                    f"Всего записей в таблице: {len(all_records)}\n"
                                    "Попробуйте:\n"
                                    "• Проверить правильность написания\n"
                                    "• Использовать часть названия (например, 'окт' вместо 'октябрьское')\n"
                                    "• Воспользоваться кнопкой '📍 Популярные населенные пункты'\n"
                                    f"• Проверить данные в таблице: https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}"
                                )
                    
                    keyboard = get_main_keyboard()
                    send_telegram_message(chat_id, response_text, keyboard)
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Ошибка в webhook: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

def format_record(record):
    """Форматирование записи для отображения"""
    do_number, kic_name = extract_kic_info(record['kic'])
    
    kic_display = record['kic']
    if do_number and kic_name:
        kic_display = f"ДО №{do_number} КИЦ {kic_name}"
    
    return (
        f"📍 Населенный пункт: {record['locality']} ({record['type']})\n\n"
        f"🏢 КИЦ: {kic_display}\n"
        f"📫 Адрес КИЦ: {record['address']}\n\n"
        f"👤 РКИЦ: {record['fio']}\n"
        f"📞 Телефон: {record['phone']}\n"
        f"📧 Email: {record['email']}\n\n"
        f"📊 Источник: Google Sheets\n"
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
    locality_map, all_records, kic_map = get_data()
    source = data_cache['source'] if data_cache and 'source' in data_cache else 'unknown'
    
    return jsonify({
        "bot_token_exists": bool(BOT_TOKEN),
        "sheet_url": PUBLIC_SHEET_URL,
        "google_sheet_id": GOOGLE_SHEET_ID,
        "gid": GOOGLE_SHEET_GID,
        "all_records_count": len(all_records),
        "locality_map_count": len(locality_map),
        "kic_count": len(kic_map),
        "cache_age_seconds": int(time.time() - cache_timestamp) if data_cache else None,
        "data_source": source,
        "first_10_records": [{"locality": r['locality'], "type": r['type'], "kic": r['kic']} for r in all_records[:10]] if all_records else [],
        "status": "running"
    })

@app.route('/test_sheet')
def test_sheet():
    """Тестирование подключения к Google Sheets"""
    try:
        response = requests.get(PUBLIC_SHEET_URL, timeout=10)
        return jsonify({
            "status_code": response.status_code,
            "content_type": response.headers.get('Content-Type'),
            "content_length": len(response.text),
            "content_preview": response.text[:500],
            "sheet_url": PUBLIC_SHEET_URL
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/search_test')
def search_test():
    """Тестирование поиска"""
    locality_map, all_records, kic_map = get_data()
    
    # Тестируем поиск разных вариантов
    test_searches = ['октябрь', 'окт', 'ктя', 'путь октября']
    results = {}
    
    for search in test_searches:
        matches = find_all_matches(all_records, search)
        results[search] = {
            "count": len(matches),
            "matches": [{"locality": r['locality'], "type": r['type'], "kic": r['kic']} for r in matches[:5]]
        }
    
    return jsonify({
        "all_records_count": len(all_records),
        "search_results": results,
        "test_searches": test_searches
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

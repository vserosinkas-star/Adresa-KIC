import os
import json
import logging
import time
from flask import Flask, request, jsonify
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Кэширование данных
data_cache = None
cache_timestamp = 0
CACHE_DURATION = 300  # 5 минут

def get_data():
    """Получение данных с кэшированием"""
    global data_cache, cache_timestamp
    
    current_time = time.time()
    
    if data_cache is None or current_time - cache_timestamp > CACHE_DURATION:
        logger.info("Updating data cache...")
        
        try:
            from gsheets import load_data_from_sheets
            sheets_data = load_data_from_sheets()
            if sheets_data:
                data_cache = sheets_data
                cache_timestamp = current_time
                logger.info(f"Data loaded from Google Sheets: {len(data_cache[0])} records")
                return data_cache
        except Exception as e:
            logger.error(f"Error loading from Google Sheets: {e}")
        
        # Fallback на mock данные
        from gsheets import MOCK_DATA
        kic_map = MOCK_DATA
        city_map = {}
        for record in MOCK_DATA.values():
            city = record['city']
            if city:
                if city not in city_map:
                    city_map[city] = []
                city_map[city].append(record)
        
        data_cache = (kic_map, city_map)
        cache_timestamp = current_time
        logger.info("Data loaded from MOCK_DATA (fallback)")
    
    return data_cache

def get_main_keyboard():
    """Клавиатура главного меню"""
    return {
        "keyboard": [
            [{"text": "🏢 Поиск по КИЦ"}, {"text": "🏙️ Поиск по городу"}],
            [{"text": "📍 Популярные города"}, {"text": "📊 Статистика"}],
            [{"text": "❓ Помощь"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_cities_keyboard():
    """Клавиатура с популярными городами"""
    TARGET_CITIES = ["Екатеринбург", "Уфа", "Челябинск", "Курган"]
    
    kic_map, city_map = get_data()
    available_cities = [city for city in TARGET_CITIES if city in city_map]
    
    if not available_cities:
        available_cities = list(city_map.keys())[:6]
    
    keyboard = []
    row = []
    for i, city in enumerate(available_cities):
        row.append({"text": city})
        if len(row) == 2 or i == len(available_cities) - 1:
            keyboard.append(row)
            row = []
    
    keyboard.append([{"text": "↩️ Назад"}])
    
    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def send_telegram_message(chat_id, text, reply_markup=None):
    """Отправка сообщения в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text
        }
        
        if reply_markup:
            payload["reply_markup"] = reply_markup
        
        response = requests.post(url, json=payload, timeout=10)
        logger.info(f"Telegram API response: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")
        return False

@app.route('/')
def home():
    return "✅ Бот куратор КИЦ работает! Используйте /start в Telegram"

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
                response_text = "👋 Привет! Я бот-куратор КИЦ. Выберите тип поиска:"
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
            
            elif text == "🏢 Поиск по КИЦ":
                response_text = "🔍 Введите код КИЦ:"
                send_telegram_message(chat_id, response_text)
            
            elif text == "🏙️ Поиск по городу":
                response_text = "🏙️ Введите название населенного пункта:"
                send_telegram_message(chat_id, response_text)
            
            elif text == "📍 Популярные города":
                response_text = "📍 Выберите населенный пункт:"
                keyboard = get_cities_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
            
            elif text == "↩️ Назад":
                response_text = "Главное меню:"
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
            
            elif text == "❓ Помощь":
                response_text = (
                    "🤖 Помощь по боту-куратору КИЦ\n\n"
                    "• Поиск по КИЦ - найти по коду клиентского центра\n"
                    "• Поиск по городу - найти все КИЦ в населенном пункте\n"
                    "• Популярные города - быстрый выбор населенных пунктов\n"
                    "• Статистика - информация о базе данных"
                )
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
            
            elif text == "📊 Статистика":
                kic_map, city_map = get_data()
                stats_text = (
                    f"📊 Статистика базы данных\n\n"
                    f"• Всего КИЦ: {len(kic_map)}\n"
                    f"• Населенных пунктов: {len(city_map)}\n"
                    f"• Обновлено: {time.strftime('%H:%M:%S')}"
                )
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, stats_text, keyboard)
            
            else:
                kic_map, city_map = get_data()
                
                # Поиск по коду КИЦ
                if text.upper() in kic_map:
                    record = kic_map[text.upper()]
                    response_text = (
                        f"✅ КИЦ {record['kic']}\n\n"
                        f"🏙️ Населенный пункт: {record['city']}\n"
                        f"📍 Адрес: {record['address']}\n"
                        f"👤 РКИЦ: {record['fio']}\n"
                        f"📞 Телефон: {record['phone']}\n"
                        f"📧 Email: {record['email']}"
                    )
                    keyboard = get_main_keyboard()
                    send_telegram_message(chat_id, response_text, keyboard)
                
                # Поиск по городу
                elif text in city_map:
                    records = city_map[text]
                    if len(records) == 1:
                        record = records[0]
                        response_text = (
                            f"✅ КИЦ {record['kic']}\n\n"
                            f"🏙️ Населенный пункт: {record['city']}\n"
                            f"📍 Адрес: {record['address']}\n"
                            f"👤 РКИЦ: {record['fio']}\n"
                            f"📞 Телефон: {record['phone']}\n"
                            f"📧 Email: {record['email']}"
                        )
                        keyboard = get_main_keyboard()
                        send_telegram_message(chat_id, response_text, keyboard)
                    else:
                        kic_list = "\n".join([f"• {r['kic']} - {r['address']}" for r in records])
                        response_text = (
                            f"📍 В населенном пункте {text} найдено {len(records)} КИЦ:\n\n"
                            f"{kic_list}\n\n"
                            f"Пожалуйста, уточните код КИЦ:"
                        )
                        send_telegram_message(chat_id, response_text)
                
                else:
                    response_text = f"❌ Не найдено КИЦ по запросу «{text}»."
                    keyboard = get_main_keyboard()
                    send_telegram_message(chat_id, response_text, keyboard)
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()})

# Vercel требует handler для serverless функций
handler = app

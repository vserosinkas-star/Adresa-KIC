from flask import Flask, request, jsonify
import os
import logging
import time
import requests

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Простые mock данные для тестирования
MOCK_DATA = {
    "KIC001": {
        "kic": "KIC001",
        "city": "Аксарка",
        "city_type": "село", 
        "address": "ул. Центральная, 15",
        "fio": "Гранкина Елена Михайловна",
        "phone": "8-909-198-88-42",
        "email": "grankina@example.com"
    },
    "KIC002": {
        "kic": "KIC002", 
        "city": "Белоярск",
        "city_type": "город",
        "address": "ул. Ленина, 25",
        "fio": "Гранкина Елена Михайловна",
        "phone": "8-909-198-88-42",
        "email": "grankina@example.com"
    }
}

def get_city_map():
    """Создаем city_map из mock данных"""
    city_map = {}
    for record in MOCK_DATA.values():
        city = record['city']
        if city not in city_map:
            city_map[city] = []
        city_map[city].append(record)
    return city_map

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
                return jsonify({"status": "ok"})
            
            elif text == "🏢 Поиск по КИЦ":
                response_text = "🔍 Введите код КИЦ (например: KIC001):"
                send_telegram_message(chat_id, response_text)
                return jsonify({"status": "ok"})
            
            elif text == "❓ Помощь":
                response_text = (
                    "🤖 Помощь по боту-куратору КИЦ\n\n"
                    "• Поиск по КИЦ - найти по коду клиентского центра\n"
                    "• Поиск по городу - найти все КИЦ в населенном пункте\n"
                    "• Статистика - информация о базе данных"
                )
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
                return jsonify({"status": "ok"})
            
            elif text == "📊 Статистика":
                city_map = get_city_map()
                stats_text = (
                    f"📊 Статистика базы данных\n\n"
                    f"• Всего КИЦ: {len(MOCK_DATA)}\n"
                    f"• Населенных пунктов: {len(city_map)}\n"
                    f"• Обновлено: {time.strftime('%H:%M:%S')}"
                )
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, stats_text, keyboard)
                return jsonify({"status": "ok"})
            
            # Поиск по КИЦ
            elif text.upper() in MOCK_DATA:
                record = MOCK_DATA[text.upper()]
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
                return jsonify({"status": "ok"})
            
            else:
                response_text = "❌ Команда не распознана. Используйте кнопки меню."
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)
                return jsonify({"status": "ok"})
        
        return jsonify({"status": "ok"})
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()})

# Vercel требует такой экспорт
if __name__ == '__main__':
    app.run(debug=True)
else:
    # Для Vercel
    application = app

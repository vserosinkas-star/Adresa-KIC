import os
import logging
import re
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

    # Если кэш устарел или отсутствует, обновляем
    if data_cache is None or current_time - cache_timestamp > CACHE_DURATION:
        logger.info("Updating data cache...")

        # Пытаемся загрузить из Google Sheets
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

        # Если Google Sheets недоступен — фолбэк на mock-данные
        try:
            from gsheets import MOCK_DATA
            location_map = {}
            for loc, recs in MOCK_DATA.items():
                location_map[loc] = recs
            data_cache = (None, location_map)  # vsp_map не используется
            cache_timestamp = current_time
            logger.info("Data loaded from MOCK_DATA (fallback)")
            return data_cache
        except Exception as e:
            logger.error(f"Error loading MOCK_DATA: {e}")

    return data_cache


def bold(text):
    return f"*{text}*"


def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "🏘️ Поиск по населённому пункту"}],
            [{"text": "📍 Популярные пункты"}, {"text": "📊 Статистика"}],
            [{"text": "❓ Помощь"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }


def get_locations_keyboard():
    """Клавиатура с популярными населёнными пунктами (Топ-6 + кнопка назад)"""
    TARGET_LOCATIONS = [
        "Новый Уренгой",
        "Салехард",
        "Нижневартовск",
        "Ханты-Мансийск",
        "Челябинск",
        "Уфа"
    ]

    _, location_map = get_data()
    available = [loc for loc in TARGET_LOCATIONS if loc in location_map][:6]

    if not available:
        available = list(location_map.keys())[:6]

    keyboard = []
    for i in range(0, len(available), 2):
        row = [{"text": loc} for loc in available[i:i + 2]]
        keyboard.append(row)
    keyboard.append([{"text": "↩️ Назад"}])

    return {
        "keyboard": keyboard,
        "resize_keyboard": True,
        "one_time_keyboard": False
    }


@app.route('/')
def home():
    return "✅ Бот куратор ВСП работает! Используйте /start в Telegram"


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
                    "👋 Привет! Я бот-куратор КИЦ.\n\n"
                    "Выберите тип поиска:"
                )
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)

            elif text == "🏘️ Поиск по населённому пункту":
                response_text = "🏘️ Введите название населённого пункта (например: *Ямбург*):"
                send_telegram_message(chat_id, response_text, parse_mode="Markdown")

            elif text == "📍 Популярные пункты":
                response_text = "🏘️ Выберите населённый пункт:"
                keyboard = get_locations_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)

            elif text == "↩️ Назад":
                response_text = "Главное меню:"
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)

            elif text == "❓ Помощь":
                response_text = (
                    "🤖 Помощь по боту-куратору КИЦ\n\n"
                    "• Поиск по населённому пункту — найти все КИЦ, обслуживающие пункт\n"
                    "• Популярные пункты — быстрый выбор часто запрашиваемых\n"
                    "• Статистика — информация о базе данных\n\n"
                    "Просто введите название населённого пункта или используйте кнопки ниже!"
                )
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, response_text, keyboard)

            elif text == "📊 Статистика":
                _, location_map = get_data()
                stats_text = (
                    f"📊 Статистика базы данных\n\n"
                    f"• Населённых пунктов: {len(location_map)}\n"
                    f"• Записей (всего): {sum(len(v) for v in location_map.values())}\n"
                    f"• Обновлено: {time.strftime('%H:%M:%S')}"
                )
                keyboard = get_main_keyboard()
                send_telegram_message(chat_id, stats_text, keyboard)

            else:
                # ==== ОСНОВНОЙ ПОИСК ПО НАСЕЛЁННОМУ ПУНКТУ ====
                _, location_map = get_data()
                records = location_map.get(text, [])

                if not records:
                    response_text = (
                        f"❌ Не найдено данных по запросу *«{text}»*.\n\n"
                        "Попробуйте уточнить название или воспользуйтесь меню:"
                    )
                    keyboard = get_main_keyboard()
                    send_telegram_message(chat_id, response_text, keyboard, parse_mode="Markdown")

                elif len(records) == 1:
                    r = records[0]
                    # Форматируем «КИЦ» с выделением
                    kic_display = f"🏢 *КИЦ* `{r['kic']}`"
                    response_text = (
                        f"✅ *{r['location']}*\n\n"
                        f"{kic_display}\n\n"
                        f"👤 {r['fio']}\n"
                        f"📞 {r['phone']}\n"
                        f"✉️ {r['email']}\n"
                        f"🏠 {r['address']}"
                    )
                    keyboard = get_main_keyboard()
                    send_telegram_message(chat_id, response_text, keyboard, parse_mode="Markdown")

                else:
                    # Несколько КИЦ на один населённый пункт (редко, но возможно)
                    response_lines = [f"✅ *{text}* — найдено {len(records)} записей:\n"]
                    for idx, r in enumerate(records, 1):
                        kic_display = f"`{r['kic']}`"
                        line = f"{idx}. 🏢 *КИЦ* {kic_display} — {r['fio']}"
                        response_lines.append(line)
                    response_text = "\n".join(response_lines)
                    keyboard = get_main_keyboard()
                    send_telegram_message(chat_id, response_text, keyboard, parse_mode="Markdown")

        return jsonify({"status": "ok"})

    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


def send_telegram_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
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
    _, location_map = get_data()
    return jsonify({
        "bot_token_exists": bool(BOT_TOKEN),
        "google_credentials_exists": bool(os.environ.get('GOOGLE_CREDENTIALS')),
        "spreadsheet_id_exists": bool(os.environ.get('SPREADSHEET_ID')),
        "locations_count": len(location_map),
        "total_records": sum(len(v) for v in location_map.values()),
        "cache_age_seconds": int(time.time() - cache_timestamp) if data_cache else None,
        "status": "running"
    })


@app.route('/refresh_cache')
def refresh_cache():
    global data_cache, cache_timestamp
    data_cache = None
    cache_timestamp = 0
    get_data()
    return jsonify({"status": "cache refreshed"})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 3000)))

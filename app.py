from http.server import BaseHTTPRequestHandler
import json
import os
import requests

# Получаем токен из переменных окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# 🔴 ЗАМЕНИТЕ ЭТО НА РЕАЛЬНЫЕ ДАННЫЕ (например, из Google Sheets, JSON или БД)
# Сейчас — для теста оставим MOCK_DATA, но структура боевая
DATA = {
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
        "city": "Краснодар",
        "city_type": "город",
        "address": "ул. Ленина, 1",
        "fio": "Иванов Иван Иванович",
        "phone": "+7-918-123-45-67",
        "email": "ivanov@example.com"
    },
    # Добавьте остальные КИЦ по шаблону
}


def send_telegram_message(chat_id, text):
    """Отправка сообщения в Telegram. Безопасно, без утечки токена."""
    if not BOT_TOKEN:
        print("[ERROR] BOT_TOKEN не задан в переменных окружения")
        return False
    try:
        # 🔴 ИСПРАВЛЕНО: НЕТ пробелов в URL → https://api.telegram.org/bot<TOKEN>/...
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"  # можно включить, если позже добавите <b>, <code> и т.д.
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"[ERROR] Telegram API: {response.status_code} — {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"[EXCEPTION] Ошибка отправки в Telegram: {e}")
        return False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Проверочный эндпоинт — должен открыться в браузере."""
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        msg = "✅ Бот куратор КИЦ работает! Используйте /start в Telegram"
        self.wfile.write(msg.encode('utf-8'))

    def do_POST(self):
        """Обработка вебхуков от Telegram."""
        try:
            # Получаем длину и тело запроса
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            update = json.loads(post_data)

            # Обрабатываем только текстовые сообщения
            if 'message' in update and 'text' in update['message']:
                chat_id = update['message']['chat']['id']
                raw_text = update['message']['text'].strip()

                # Нормализуем ввод: убираем лишние пробелы, приводим к верхнему регистру
                clean_text = raw_text.upper().replace(' ', '').replace('-', '')

                # Логика ответа
                if raw_text == '/start':
                    reply = (
                        "👋 Привет! Я <b>бот-куратор КИЦ</b>.\n\n"
                        "🔍 Введите код КИЦ (например: <code>KIC001</code>)\n"
                        "📌 Подсказка: можно вводить и с маленькой буквы, и с пробелами."
                    )
                    send_telegram_message(chat_id, reply)
                elif clean_text in DATA:
                    r = DATA[clean_text]
                    reply = (
                        f"✅ <b>КИЦ {r['kic']}</b>\n\n"
                        f"🏘 Город: <b>{r['city']}</b> ({r['city_type']})\n"
                        f"📍 Адрес: {r['address']}\n"
                        f"👤 РКИЦ: <b>{r['fio']}</b>\n"
                        f"📞 Телефон: {r['phone']}"
                    )
                    send_telegram_message(chat_id, reply)
                else:
                    reply = (
                        f"❌ КИЦ <code>{raw_text}</code> не найден.\n"
                        f"📝 Попробуйте: <code>KIC001</code>, <code>KIC002</code>"
                    )
                    send_telegram_message(chat_id, reply)

            # Telegram требует 200 OK для подтверждения получения вебхука
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))

        except json.JSONDecodeError:
            print("[ERROR] Invalid JSON in POST body")
            self.send_response(400)
            self.end_headers()
        except Exception as e:
            print(f"[CRITICAL] Ошибка в do_POST: {e}")
            self.send_response(500)
            self.end_headers()


# Точка входа для Vercel
handler = Handler

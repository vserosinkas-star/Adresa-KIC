from http.server import BaseHTTPRequestHandler
import json
import os
import requests

print("[DEBUG] GOOGLE_SHEETS_CREDENTIALS length:", len(GOOGLE_CREDENTIALS_JSON or ""))
print("[DEBUG] First 50 chars:", (GOOGLE_CREDENTIALS_JSON or "")[:50])

# === Конфигурация ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
SPREADSHEET_ID = "1h6dMEWsLcH--d4MB5CByx05xitOwhAGV"
SHEET_GID = "1532223079"  # gid из URL
RANGE = f"Общий!A1:G1000"  # ← замените "Лист1" на имя вашего листа

# Получаем учётные данные из переменной окружения
GOOGLE_CREDENTIALS_JSON = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
if not GOOGLE_CREDENTIALS_JSON:
    raise RuntimeError("❌ Переменная GOOGLE_SHEETS_CREDENTIALS не задана")

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    raise RuntimeError("❌ Установите зависимости: gspread, google-auth")

# Инициализация клиента Google Sheets (выполняется при импорте → кэшируется)
try:
    creds = Credentials.from_service_account_info(
        json.loads(GOOGLE_CREDENTIALS_JSON),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet_by_gid(int(SHEET_GID))
except Exception as e:
    print(f"[CRITICAL] Ошибка подключения к Google Sheets: {e}")
    sheet = None


def load_data_from_sheets():
    """Загружает данные из Google Sheets и возвращает dict: {kic: record}"""
    if not sheet:
        return {}
    try:
        rows = sheet.get_all_values()
        if not rows:
            return {}
        # Первая строка — заголовки
        headers = rows[0]
        data = {}
        for row in rows[1:]:
            if len(row) < 7:  # ожидаем минимум 7 колонок
                continue
            # Порядок колонок: kic, city, city_type, address, fio, phone, email
            record = {
                "kic": row[0].strip(),
                "city": row[1].strip(),
                "city_type": row[2].strip(),
                "address": row[3].strip(),
                "fio": row[4].strip(),
                "phone": row[5].strip(),
                "email": row[6].strip(),
            }
            key = record["kic"].upper()
            if key:
                data[key] = record
        return data
    except Exception as e:
        print(f"[ERROR] Ошибка загрузки данных: {e}")
        return {}


# Кэшируем данные при старте (можно обновлять раз в N минут, если нужно)
DATA = load_data_from_sheets()


def send_telegram_message(chat_id, text):
    if not BOT_TOKEN:
        print("[ERROR] BOT_TOKEN не задан")
        return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            print(f"[TG ERROR] {response.status_code}: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"[TG EXCEPTION] {e}")
        return False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        msg = f"✅ Бот работает! Загружено КИЦ: {len(DATA)}\nИспользуйте /start в Telegram"
        self.wfile.write(msg.encode('utf-8'))

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            update = json.loads(post_data)

            if 'message' in update and 'text' in update['message']:
                chat_id = update['message']['chat']['id']
                raw_text = update['message']['text'].strip()
                clean_key = raw_text.upper().replace(' ', '').replace('-', '')

                if raw_text == '/start':
                    reply = (
                        "👋 Привет! Я <b>бот Адреса КИЦ</b>.\n\n"
                        "🔍 Введите код КИЦ (например: <code>KIC001</code>)"
                    )
                    send_telegram_message(chat_id, reply)
                elif clean_key in DATA:
                    r = DATA[clean_key]
                    reply = (
                        f"✅ <b>КИЦ {r['kic']}</b>\n\n"
                        f"🏘 Город: <b>{r['city']}</b> ({r['city_type']})\n"
                        f"📍 Адрес: {r['address']}\n"
                        f"👤 РКИЦ: <b>{r['fio']}</b>\n"
                        f"📞 Телефон: {r['phone']}"
                    )
                    send_telegram_message(chat_id, reply)
                else:
                    reply = f"❌ КИЦ <code>{raw_text}</code> не найден. Всего загружено: {len(DATA)}"
                    send_telegram_message(chat_id, reply)

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))

        except Exception as e:
            print(f"[POST ERROR] {e}")
            self.send_response(500)
            self.end_headers()


handler = Handler

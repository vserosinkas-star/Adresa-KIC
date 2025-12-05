from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import re

# === Настройки ===
BOT_TOKEN = os.environ.get('BOT_TOKEN')
GOOGLE_SHEET_ID = "1h6dMEWsLcH--d4MB5CByx05xitOwhAGV"

# Тестовые данные
TEST_DATA = {
    "KIC001": {"kic": "KIC001", "city": "Аксарка", "address": "ул. Центральная, 15", "fio": "Гранкина Елена", "phone": "8-909-198-88-42"},
    "KIC002": {"kic": "KIC002", "city": "Краснодар", "address": "ул. Ленина, 1", "fio": "Иванов Иван", "phone": "+7-918-123-45-67"},
}

def check_environment():
    """Проверяем переменные окружения"""
    results = []
    
    # Проверка BOT_TOKEN
    if BOT_TOKEN:
        results.append(("✅", "BOT_TOKEN установлен"))
    else:
        results.append(("❌", "BOT_TOKEN не установлен"))
    
    # Проверка GOOGLE_SERVICE_ACCOUNT
    google_sa = os.environ.get('GOOGLE_SERVICE_ACCOUNT')
    if google_sa:
        try:
            # Пробуем распарсить JSON
            sa_info = json.loads(google_sa)
            email = sa_info.get('client_email', 'Неизвестный email')
            results.append(("✅", f"GOOGLE_SERVICE_ACCOUNT: {email}"))
        except:
            results.append(("❌", "GOOGLE_SERVICE_ACCOUNT: Неверный формат JSON"))
    else:
        results.append(("❌", "GOOGLE_SERVICE_ACCOUNT не установлен"))
    
    return results

def get_data():
    """Возвращает данные"""
    return TEST_DATA, "тестовые данные"

def send_telegram_message(chat_id, text):
    """Отправляет сообщение в Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
        return True
    except Exception as e:
        print(f"Ошибка Telegram: {e}")
        return False

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Обработчик GET запросов"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        
        data, source = get_data()
        env_checks = check_environment()
        
        # Создаем HTML
        html = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Бот-куратор КИЦ</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }
        .success { color: green; }
        .error { color: red; }
        .warning { color: orange; }
        .box { background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 15px 0; }
        code { background: #eee; padding: 2px 5px; border-radius: 3px; }
        .instruction { background: #e8f4fc; border-left: 4px solid #2196F3; padding: 15px; margin: 15px 0; }
        ol { margin-left: 20px; }
        li { margin: 10px 0; }
    </style>
</head>
<body>
    <h1>🤖 Бот-куратор КИЦ</h1>
    
    <div class="box">
        <h3>📊 Статус системы</h3>'''
        
        for icon, message in env_checks:
            html += f'<p>{icon} {message}</p>'
        
        html += f'''
        <p>Данные: {source}</p>
        <p>Записей: {len(data)}</p>
    </div>
    
    <div class="box">
        <h3>📝 Примеры запросов в Telegram:</h3>
        <p><code>/start</code> - начало работы</p>
        <p><code>/status</code> - проверка статуса</p>
        <p><code>KIC001</code> - тест поиска</p>
        <p><code>KIC002</code> - тест поиска</p>
    </div>'''
        
        # Показываем инструкцию, если нет GOOGLE_SERVICE_ACCOUNT
        if not os.environ.get('GOOGLE_SERVICE_ACCOUNT'):
            html += '''
    <div class="instruction">
        <h3>📖 Инструкция по добавлению Google Sheets</h3>
        <p>Чтобы подключить Google Sheets, выполните следующие шаги:</p>
        <ol>
            <li><strong>Создайте JSON ключ сервисного аккаунта:</strong>
                <br>• Зайдите в <a href="https://console.cloud.google.com/" target="_blank">Google Cloud Console</a>
                <br>• Создайте сервисный аккаунт
                <br>• Скачайте JSON ключ</li>
            <li><strong>Добавьте переменную в Vercel:</strong>
                <br>• Откройте проект в <a href="https://vercel.com" target="_blank">Vercel</a>
                <br>• Settings → Environment Variables
                <br>• Добавьте переменную:
                <br>  <strong>Name:</strong> GOOGLE_SERVICE_ACCOUNT
                <br>  <strong>Value:</strong> <em>весь JSON файл одной строкой</em></li>
            <li><strong>Предоставьте доступ к таблице:</strong>
                <br>• Откройте <a href="https://docs.google.com/spreadsheets/d/1h6dMEWsLcH--d4MB5CByx05xitOwhAGV/edit" target="_blank">таблицу</a>
                <br>• Нажмите "Настройки доступа"
                <br>• Добавьте email сервисного аккаунта (из JSON)
                <br>• Дайте права "Редактор"</li>
            <li><strong>Переразверните проект:</strong>
                <br>• В Vercel нажмите "Deployments"
                <br>• Выберите последний деплой
                <br>• Нажмите "Redeploy"</li>
        </ol>
    </div>'''
        
        html += '''
    <div class="box">
        <h3>🔗 Полезные ссылки</h3>
        <p><a href="https://docs.google.com/spreadsheets/d/1h6dMEWsLcH--d4MB5CByx05xitOwhAGV/edit" target="_blank">
            📁 Открыть таблицу Google Sheets
        </a></p>
        <p><a href="https://vercel.com" target="_blank">
            ⚙️ Панель управления Vercel
        </a></p>
    </div>
</body>
</html>'''
        
        self.wfile.write(html.encode('utf-8'))
    
    def do_POST(self):
        """Обработчик POST запросов от Telegram"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            update = json.loads(post_data)

            if 'message' in update and 'text' in update['message']:
                chat_id = update['message']['chat']['id']
                raw_text = update['message']['text'].strip()
                
                print(f"Сообщение от {chat_id}: {raw_text}")
                
                # Получаем данные
                data, source = get_data()
                
                # Нормализуем ввод
                key = re.sub(r'[^\w]', '', raw_text.upper())
                
                if raw_text == '/start':
                    reply = (
                        "👋 <b>Привет! Я бот-куратор КИЦ</b>\n\n"
                        "🔍 <b>Как использовать:</b>\n"
                        "Введите код КИЦ для получения информации\n\n"
                        "<b>Примеры:</b>\n"
                        "<code>KIC001</code>\n"
                        "<code>KIC002</code>\n\n"
                        f"📊 <b>Статус:</b> Работает с {source}"
                    )
                    
                elif raw_text == '/status':
                    env_checks = check_environment()
                    reply = "📊 <b>Статус системы:</b>\n\n"
                    for icon, message in env_checks:
                        reply += f"{icon} {message}\n"
                    reply += f"\n📁 Данные: {source}\n"
                    reply += f"📈 Записей: {len(data)}"
                    
                elif raw_text == '/help':
                    reply = (
                        "📚 <b>Справка по боту:</b>\n\n"
                        "• Введите код КИЦ для поиска\n"
                        "• Регистр и пробелы не важны\n\n"
                        "⚙️ <b>Команды:</b>\n"
                        "/start - начало работы\n"
                        "/status - статус системы\n"
                        "/help - эта справка\n\n"
                        "💡 <b>Примеры:</b>\n"
                        "<code>KIC001</code>\n"
                        "<code>KIC 002</code>\n"
                        "<code>kic-001</code>"
                    )
                    
                else:
                    # Ищем в данных
                    if key in data:
                        r = data[key]
                        reply = (
                            f"✅ <b>КИЦ {r['kic']}</b>\n\n"
                            f"🏘 <b>Город:</b> {r['city']}\n"
                            f"📍 <b>Адрес:</b> {r['address']}\n"
                            f"👤 <b>Ответственный:</b> {r['fio']}\n"
                            f"📞 <b>Телефон:</b> {r['phone']}\n\n"
                            f"<i>Данные из: {source}</i>"
                        )
                    else:
                        # Показываем доступные коды
                        examples = []
                        for k in list(data.keys())[:5]:
                            examples.append(f"<code>{data[k]['kic']}</code>")
                        
                        reply = f"❌ КИЦ <code>{raw_text}</code> не найден.\n\n"
                        if examples:
                            reply += f"<b>Доступные коды:</b>\n" + "\n".join(examples)
                        else:
                            reply += "Нет доступных записей."
                
                send_telegram_message(chat_id, reply)

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode('utf-8'))

        except Exception as e:
            print(f"Ошибка обработки: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

handler = Handler

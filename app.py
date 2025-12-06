import json
import os
import requests

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')

TEST_DATA = {
    "НОВЫЙ УРЕНГОЙ": {
        "city": "Новый Уренгой",
        "city_type": "Город",
        "kic": "ДО №8369/018 КИЦ Новоуренгойский",
        "address": "629300, г. Новый Уренгой, мкр. Дружба, 3",
        "fio": "Мохначёв Сергей Вячеславович",
        "phone": "929-252-0303",
        "email": "Mokhnachov.S.V@sberbank.ru"
    }
}

def send_telegram_message(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=5)
        return True
    except:
        return False

def handler(event, context=None):
    method = event.get('httpMethod', 'GET')
    
    if method == 'GET':
        html = '''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Бот-куратор КИЦ</title></head>
<body>
<h1>🤖 Бот-куратор КИЦ</h1>
<p>✅ Бот работает</p>
<p>📍 Населенных пунктов: 1</p>
<p>🔍 В Telegram: <code>/start</code> или <code>Новый Уренгой</code></p>
</body></html>'''
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'text/html; charset=utf-8'},
            'body': html
        }
    
    elif method == 'POST':
        try:
            body = event.get('body', '{}')
            update = json.loads(body if isinstance(body, str) else body.decode())
            
            if 'message' in update:
                chat_id = update['message']['chat']['id']
                text = update['message']['text'].strip()
                
                if text.lower() == '/start':
                    reply = "👋 Привет! Я бот-куратор КИЦ\nВведите название города"
                elif 'уренгой' in text.lower():
                    city = TEST_DATA['НОВЫЙ УРЕНГОЙ']
                    reply = f"""📍 <b>{city['city']}</b> ({city['city_type']})
🏢 КИЦ: {city['kic']}
📌 Адрес: {city['address']}
👤 Ответственный: {city['fio']}
📞 Телефон: {city['phone']}
📧 Email: {city['email']}"""
                else:
                    reply = f"❌ Город '{text}' не найден\nПопробуйте: Новый Уренгой"
                
                send_telegram_message(chat_id, reply)
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'ok': True})
            }
        except Exception as e:
            return {
                'statusCode': 500,
                'body': json.dumps({'ok': False, 'error': str(e)})
            }
    
    return {
        'statusCode': 405,
        'body': json.dumps({'error': 'Method not allowed'})
    }

from http.server import BaseHTTPRequestHandler
import json
import os
import requests
import gspread
from google.oauth2.service_account import Credentials
import re
import base64

BOT_TOKEN = os.environ.get('BOT_TOKEN')
SHEET_ID = "1h6dMEWsLcH--d4MB5CByx05xitOwhAGV"
@@ -33,10 +34,25 @@
def load_google_sheets():
    """Загружает данные из Google Sheets"""
    try:
        # Проверяем наличие переменной
        # Проверяем наличие переменной - несколько вариантов
        sa_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT')
        
        # Если переменная пустая, проверяем альтернативные имена
        if not sa_json:
            sa_json = os.environ.get('GOOGLE_CREDENTIALS')
        
        if not sa_json:
            return None, "GOOGLE_SERVICE_ACCOUNT не найден"
            return None, "GOOGLE_SERVICE_ACCOUNT не найден в переменных окружения"
        
        # Пробуем декодировать как base64 (если закодировано)
        try:
            sa_json = base64.b64decode(sa_json).decode('utf-8')
        except:
            # Если не base64, используем как есть
            pass
        
        # Очищаем от лишних символов
        sa_json = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', sa_json)

        # Парсим JSON
        sa_info = json.loads(sa_json)
@@ -60,7 +76,6 @@

        # Получаем заголовки
        headers = [str(h).strip() for h in all_values[0]]
        print(f"Найдены заголовки: {headers}")

        # Определяем индексы колонок
        col_index = {}
@@ -81,8 +96,6 @@
            elif 'email ркиц' in header_lower or 'email' in header_lower:
                col_index['email'] = i

        print(f"Индексы колонок: {col_index}")
        
        # Проверяем необходимые колонки
        required_cols = ['city', 'kic']
        missing_cols = [col for col in required_cols if col not in col_index]
@@ -104,46 +117,43 @@
                # Создаем запись
                entry = {
                    "city": city_value,
                    "city_type": row[col_index.get('city_type', col_index['city'])].strip() 
                               if col_index.get('city_type', col_index['city']) < len(row) else "",
                    "city_type": row[col_index.get('city_type', 0)].strip() 
                               if col_index.get('city_type', 0) < len(row) else "",
                    "kic": row[col_index['kic']].strip() if col_index['kic'] < len(row) else "",
                    "address": row[col_index.get('address', col_index['kic'])].strip() 
                              if col_index.get('address', col_index['kic']) < len(row) else "",
                    "fio": row[col_index.get('fio', col_index['kic'])].strip() 
                           if col_index.get('fio', col_index['kic']) < len(row) else "",
                    "phone": row[col_index.get('phone', col_index['kic'])].strip() 
                            if col_index.get('phone', col_index['kic']) < len(row) else "",
                    "email": row[col_index.get('email', col_index['kic'])].strip() 
                            if col_index.get('email', col_index['kic']) < len(row) else ""
                    "address": row[col_index.get('address', 0)].strip() 
                              if col_index.get('address', 0) < len(row) else "",
                    "fio": row[col_index.get('fio', 0)].strip() 
                           if col_index.get('fio', 0) < len(row) else "",
                    "phone": row[col_index.get('phone', 0)].strip() 
                            if col_index.get('phone', 0) < len(row) else "",
                    "email": row[col_index.get('email', 0)].strip() 
                            if col_index.get('email', 0) < len(row) else ""
                }

                result[key] = entry

            except Exception as e:
                print(f"Ошибка обработки строки: {e}")
                continue

        if not result:
            return None, "Не найдено ни одной записи"

        return result, f"Успешно загружено {len(result)} населенных пунктов"

    except json.JSONDecodeError as e:
        return None, f"Ошибка формата JSON: {str(e)[:100]}"
    except Exception as e:
        return None, f"Ошибка: {str(e)}"
        return None, f"Ошибка подключения: {str(e)[:100]}"

def normalize_city_name(city_name):
    """Нормализует название населенного пункта для поиска"""
    # Убираем лишние символы, приводим к верхнему регистру
    normalized = re.sub(r'[^\w\s-]', '', str(city_name).upper())
    # Заменяем несколько пробелов на один
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

def normalize_search_query(query):
    """Нормализует поисковый запрос"""
    # Убираем лишние символы, приводим к верхнему регистру
    normalized = re.sub(r'[^\w\s-]', '', str(query).upper())
    # Заменяем несколько пробелов на один
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized

@@ -160,7 +170,7 @@
        if normalized_query in city_key or city_key in normalized_query:
            return city_data

        # Проверяем русское название (без транслитерации)
        # Проверяем русское название
        if city_data.get('city', '').upper() == normalized_query:
            return city_data

@@ -184,6 +194,27 @@
        print(f"Ошибка отправки в Telegram: {e}")
        return False

def format_city_response(city_data, source):
    """Форматирует ответ с информацией о населенном пункте"""
    reply = f"📍 <b>{city_data['city']}</b>"
    if city_data.get('city_type'):
        reply += f" ({city_data['city_type']})"
    reply += "\n\n"
    
    if city_data.get('kic'):
        reply += f"🏢 <b>КИЦ:</b> {city_data['kic']}\n"
    if city_data.get('address'):
        reply += f"📌 <b>Адрес КИЦ:</b> {city_data['address']}\n"
    if city_data.get('fio'):
        reply += f"👤 <b>Ответственный:</b> {city_data['fio']}\n"
    if city_data.get('phone'):
        reply += f"📞 <b>Телефон:</b> {city_data['phone']}\n"
    if city_data.get('email'):
        reply += f"📧 <b>Email:</b> {city_data['email']}"
    
    reply += f"\n\n📋 <i>Данные из: {source}</i>"
    return reply

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Отключаем стандартное логирование"""
@@ -322,16 +353,14 @@
                    )

                elif raw_text.lower().startswith('/search'):
                    # Команда поиска /search ГОРОД
                    search_query = raw_text[7:].strip()  # Убираем '/search'
                    search_query = raw_text[7:].strip()
                    if not search_query:
                        reply = "❌ Укажите название населенного пункта после команды /search\n\nПример: <code>/search Новый Уренгой</code>"
                    else:
                        city_data = find_city(data, search_query)
                        if city_data:
                            reply = format_city_response(city_data, source)
                        else:
                            # Показываем доступные населенные пункты
                            examples = []
                            for city_key, city_info in list(data.items())[:8]:
                                examples.append(f"<code>{city_info['city']}</code>")
@@ -342,7 +371,6 @@
                                reply += f"\n<b>Примеры:</b>\n" + "\n".join(examples)

                elif raw_text.lower() == '/list':
                    # Показать список всех населенных пунктов
                    if len(data) <= 20:
                        reply = "📍 <b>Все населенные пункты в базе:</b>\n\n"
                        for city_key, city_info in data.items():
@@ -355,12 +383,10 @@
                        reply += f"\n... и еще {len(data) - 20} населенных пунктов"

                else:
                    # Обычный поиск по населенному пункту
                    city_data = find_city(data, raw_text)
                    if city_data:
                        reply = format_city_response(city_data, source)
                    else:
                        # Показываем доступные населенные пункты
                        examples = []
                        for city_key, city_info in list(data.items())[:8]:
                            examples.append(f"<code>{city_info['city']}</code>")
@@ -382,25 +408,4 @@
            self.send_response(500)
            self.end_headers()

def format_city_response(city_data, source):
    """Форматирует ответ с информацией о населенном пункте"""
    reply = f"📍 <b>{city_data['city']}</b>"
    if city_data.get('city_type'):
        reply += f" ({city_data['city_type']})"
    reply += "\n\n"
    
    if city_data.get('kic'):
        reply += f"🏢 <b>КИЦ:</b> {city_data['kic']}\n"
    if city_data.get('address'):
        reply += f"📌 <b>Адрес КИЦ:</b> {city_data['address']}\n"
    if city_data.get('fio'):
        reply += f"👤 <b>Ответственный:</b> {city_data['fio']}\n"
    if city_data.get('phone'):
        reply += f"📞 <b>Телефон:</b> {city_data['phone']}\n"
    if city_data.get('email'):
        reply += f"📧 <b>Email:</b> {city_data['email']}"
    
    reply += f"\n\n📋 <i>Данные из: {source}</i>"
    return reply

handler = Handler

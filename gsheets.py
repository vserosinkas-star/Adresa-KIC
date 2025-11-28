import os
import json
import logging
import gspread
from google.oauth2.service_account import Credentials

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock данные для fallback под новую структуру
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
    },
    "KIC003": {
        "kic": "KIC003",
        "city": "Салехард", 
        "city_type": "город",
        "address": "ул. Республики, 42",
        "fio": "Гранкина Елена Михайловна",
        "phone": "8-909-198-88-42",
        "email": "grankina@example.com"
    },
    "KIC004": {
        "kic": "KIC004",
        "city": "Лабытнанги",
        "city_type": "город",
        "address": "ул. Первомайская, 10",
        "fio": "Гранкина Елена Михайловна", 
        "phone": "8-909-198-88-42",
        "email": "grankina@example.com"
    },
    "KIC005": {
        "kic": "KIC005",
        "city": "Харп",
        "city_type": "поселок",
        "address": "ул. Школьная, 5",
        "fio": "Гранкина Елена Михайловна",
        "phone": "8-909-198-88-42",
        "email": "grankina@example.com"
    }
}

def init_gsheets():
    """Инициализация Google Sheets"""
    try:
        # Получаем credentials из переменной окружения
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
        if not credentials_json:
            logger.error("GOOGLE_CREDENTIALS not found in environment variables")
            return None
            
        # Парсим JSON
        creds_dict = json.loads(credentials_json)
        
        # Настраиваем авторизацию
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        logger.info("Google Sheets client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Google Sheets init error: {e}")
        return None

def load_data_from_sheets():
    """Загрузка данных из Google Sheets для новой структуры"""
    try:
        client = init_gsheets()
        if not client:
            return None
            
        SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
        if not SPREADSHEET_ID:
            return None
            
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.sheet1
        
        # Получаем все значения
        all_values = sheet.get_all_values()
        logger.info(f"Raw data: {len(all_values)} rows")
        
        if len(all_values) < 2:  # Только заголовок или пусто
            logger.warning("Not enough data in sheet")
            return None
        
        kic_map = {}
        city_map = {}
        
        # Автоопределение структуры по заголовкам для новой схемы
        headers = [h.lower().strip() for h in all_values[0]]
        logger.info(f"Detected headers: {headers}")
        
        # Определяем индексы столбцов для новой структуры
        city_idx = None
        city_type_idx = None
        kic_idx = None
        address_idx = None
        fio_idx = None
        phone_idx = None
        email_idx = None
        
        for i, header in enumerate(headers):
            header_lower = header.lower()
            if any(word in header_lower for word in ['населенный', 'город', 'населённый']):
                city_idx = i
            elif any(word in header_lower for word in ['тип', 'type']):
                city_type_idx = i
            elif any(word in header_lower for word in ['киц', 'kic', 'код']):
                kic_idx = i
            elif any(word in header_lower for word in ['адрес', 'address']):
                address_idx = i
            elif any(word in header_lower for word in ['фио', 'fio', 'имя', 'name', 'ркиц']):
                fio_idx = i
            elif any(word in header_lower for word in ['телефон', 'phone', 'тел.']):
                phone_idx = i
            elif any(word in header_lower for word in ['email', 'e-mail', 'почта']):
                email_idx = i
        
        # Если не нашли стандартные заголовки, используем предположения по порядку
        if city_idx is None: city_idx = 0
        if city_type_idx is None: city_type_idx = 1
        if kic_idx is None: kic_idx = 2
        if address_idx is None: address_idx = 3
        if fio_idx is None: fio_idx = 4
        if phone_idx is None: phone_idx = 5
        if email_idx is None: email_idx = 6
        
        logger.info(f"Using column indices - City: {city_idx}, City Type: {city_type_idx}, KIC: {kic_idx}, Address: {address_idx}, FIO: {fio_idx}, Phone: {phone_idx}, Email: {email_idx}")
        
        # Обрабатываем данные
        for i, row in enumerate(all_values[1:], start=2):  # Пропускаем заголовок
            if len(row) > max(city_idx, city_type_idx, kic_idx, address_idx, fio_idx, phone_idx, email_idx):
                city = str(row[city_idx]).strip() if city_idx < len(row) and row[city_idx] else ''
                city_type = str(row[city_type_idx]).strip() if city_type_idx < len(row) and row[city_type_idx] else ''
                kic = str(row[kic_idx]).strip() if kic_idx < len(row) and row[kic_idx] else ''
                address = str(row[address_idx]).strip() if address_idx < len(row) and row[address_idx] else ''
                fio = str(row[fio_idx]).strip() if fio_idx < len(row) and row[fio_idx] else ''
                phone = str(row[phone_idx]).strip() if phone_idx < len(row) and row[phone_idx] else ''
                email = str(row[email_idx]).strip() if email_idx < len(row) and row[email_idx] else ''
                
                kic = normalize_kic_code(kic)
                
                if kic and fio:
                    record = {
                        'kic': kic,
                        'city': city,
                        'city_type': city_type,
                        'address': address,
                        'fio': fio,
                        'phone': phone,
                        'email': email
                    }
                    kic_map[kic] = record
                    
                    if city:
                        if city not in city_map:
                            city_map[city] = []
                        city_map[city].append(record)
            else:
                logger.warning(f"Row {i} has insufficient columns: {row}")
        
        logger.info(f"Processed {len(kic_map)} records from Google Sheets")
        return kic_map, city_map
        
    except Exception as e:
        logger.error(f"Error loading data from Google Sheets: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def normalize_kic_code(kic_raw):
    """Нормализация кода КИЦ"""
    if not kic_raw:
        return ""
    
    # Удаляем лишние пробелы и приводим к верхнему регистру
    kic = kic_raw.strip().upper()
    
    return kic

def test_connection():
    """Тест подключения к Google Sheets"""
    try:
        client = init_gsheets()
        if not client:
            return {"success": False, "error": "Failed to initialize client"}
            
        SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
        if not SPREADSHEET_ID:
            return {"success": False, "error": "SPREADSHEET_ID not found"}
            
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.sheet1
        
        # Проверяем доступ
        title = spreadsheet.title
        url = spreadsheet.url
        
        # Получаем заголовки для проверки структуры
        headers = sheet.row_values(1)
        
        return {
            "success": True,
            "spreadsheet_title": title,
            "spreadsheet_url": url,
            "sheet_title": sheet.title,
            "headers": headers,
            "expected_headers": [
                "Населенный пункт", "Тип населенного пункта", "КИЦ", 
                "Адрес КИЦ", "ФИО РКИЦ", "Телефон РКИЦ", "Email РКИЦ"
            ]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

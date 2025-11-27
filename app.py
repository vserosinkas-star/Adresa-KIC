import os
import gspread
from google.oauth2.service_account import Credentials
import logging

logger = logging.getLogger(__name__)

# MOCK данные под новую структуру
MOCK_DATA = {
    "KIC001": {
        'kic': 'KIC001',
        'city': 'Екатеринбург',
        'city_type': 'город',
        'address': 'ул. Ленина, 1',
        'fio': 'Иванов Иван Иванович',
        'phone': '+7-999-123-45-67',
        'email': 'ivanov@example.com'
    },
    "KIC002": {
        'kic': 'KIC002',
        'city': 'Уфа',
        'city_type': 'город',
        'address': 'ул. Советская, 25',
        'fio': 'Петров Петр Петрович',
        'phone': '+7-999-765-43-21',
        'email': 'petrov@example.com'
    }
}

def init_gsheets():
    """Инициализация клиента Google Sheets"""
    try:
        credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
        if not credentials_json:
            logger.error("GOOGLE_CREDENTIALS environment variable not set")
            return None
            
        creds_dict = eval(credentials_json)
        creds = Credentials.from_service_account_info(creds_dict)
        scoped_creds = creds.with_scopes([
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(scoped_creds)
        logger.info("Google Sheets client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Error initializing Google Sheets client: {e}")
        return None

def load_data_from_sheets():
    """Загрузка данных из Google Sheets с новой структурой"""
    try:
        client = init_gsheets()
        if not client:
            return None
            
        SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
        if not SPREADSHEET_ID:
            logger.error("SPREADSHEET_ID environment variable not set")
            return None
            
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.sheet1
        
        # Получаем все данные
        all_data = sheet.get_all_records()
        
        kic_map = {}
        city_map = {}
        
        for row in all_data:
            # Предполагаемая структура колонок:
            # Населенный пункт | Тип населенного пункта | КИЦ | Адрес КИЦ | ФИО РКИЦ | Телефон РКИЦ | Email РКИЦ
            kic_code = row.get('КИЦ', '')
            if kic_code:
                record = {
                    'kic': kic_code,
                    'city': row.get('Населенный пункт', ''),
                    'city_type': row.get('Тип населенного пункта', ''),
                    'address': row.get('Адрес КИЦ', ''),
                    'fio': row.get('ФИО РКИЦ', ''),
                    'phone': row.get('Телефон РКИЦ', ''),
                    'email': row.get('Email РКИЦ', '')
                }
                
                kic_map[kic_code] = record
                
                # Добавляем в city_map
                city = record['city']
                if city:
                    if city not in city_map:
                        city_map[city] = []
                    city_map[city].append(record)
        
        logger.info(f"Loaded {len(kic_map)} KIC records and {len(city_map)} cities")
        return kic_map, city_map
        
    except Exception as e:
        logger.error(f"Error loading data from Google Sheets: {e}")
        return None

def test_connection():
    """Тест подключения к Google Sheets"""
    try:
        client = init_gsheets()
        if not client:
            return {"success": False, "error": "Failed to initialize client"}
            
        SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
        if not SPREADSHEET_ID:
            return {"success": False, "error": "SPREADSHEET_ID not set"}
            
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        sheet = spreadsheet.sheet1
        
        # Пытаемся получить заголовки
        headers = sheet.row_values(1)
        
        return {
            "success": True,
            "spreadsheet_title": spreadsheet.title,
            "sheet_title": sheet.title,
            "headers": headers,
            "expected_headers": [
                "Населенный пункт", "Тип населенного пункта", "КИЦ", 
                "Адрес КИЦ", "ФИО РКИЦ", "Телефон РКИЦ", "Email РКИЦ"
            ]
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

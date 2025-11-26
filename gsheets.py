import os
import json
import logging
import gspread
from google.oauth2.service_account import Credentials

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock данные для fallback
MOCK_DATA = {
    "8369/067": {
        "vsp": "8369/067", 
        "fio": "Гранкина Елена Михайловна",
        "contact": "8-5459-10-10",
        "mobile": "8-909-198-88-42",
        "city": "Аксарка"
    },
    "8369/068": {
        "vsp": "8369/068",
        "fio": "Гранкина Елена Михайловна", 
        "contact": "8-5459-10-10",
        "mobile": "8-909-198-88-42",
        "city": "Белоярск"
    },
    "8369/069": {
        "vsp": "8369/069",
        "fio": "Гранкина Елена Михайловна",
        "contact": "8-5459-10-10",
        "mobile": "8-909-198-88-42",
        "city": "Салехард"
    },
    "8369/070": {
        "vsp": "8369/070",
        "fio": "Гранкина Елена Михайловна",
        "contact": "8-5459-10-10",
        "mobile": "8-909-198-88-42",
        "city": "Лабытнанги"
    },
    "8369/071": {
        "vsp": "8369/071",
        "fio": "Гранкина Елена Михайловна",
        "contact": "8-5459-10-10",
        "mobile": "8-909-198-88-42",
        "city": "Харп"
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
    """Улучшенная загрузка данных с обработкой разных форматов"""
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
        
        vsp_map = {}
        city_map = {}
        
        # Автоопределение структуры по заголовкам
        headers = [h.lower().strip() for h in all_values[0]]
        logger.info(f"Detected headers: {headers}")
        
        # Определяем индексы столбцов
        vsp_idx = None
        fio_idx = None
        contact_idx = None
        mobile_idx = None
        city_idx = None
        
        for i, header in enumerate(headers):
            if any(word in header for word in ['всп', 'vsp', 'код']):
                vsp_idx = i
            elif any(word in header for word in ['фио', 'fio', 'имя', 'name']):
                fio_idx = i
            elif any(word in header for word in ['контакт', 'contact', 'телеграм', 'telegram']):
                contact_idx = i
            elif any(word in header for word in ['мобильный', 'mobile', 'телефон', 'phone']):
                mobile_idx = i
            elif any(word in header for word in ['город', 'city', 'город']):
                city_idx = i
        
        # Если не нашли стандартные заголовки, используем предположения
        if vsp_idx is None: vsp_idx = 0
        if fio_idx is None: fio_idx = 1
        if contact_idx is None: contact_idx = 2
        if mobile_idx is None: mobile_idx = 3
        if city_idx is None: city_idx = 4
        
        logger.info(f"Using column indices - VSP: {vsp_idx}, FIO: {fio_idx}, Contact: {contact_idx}, Mobile: {mobile_idx}, City: {city_idx}")
        
        # Обрабатываем данные
        for i, row in enumerate(all_values[1:], start=2):  # Пропускаем заголовок
            if len(row) > max(vsp_idx, fio_idx, contact_idx, mobile_idx, city_idx):
                vsp = str(row[vsp_idx]).strip() if vsp_idx < len(row) and row[vsp_idx] else ''
                fio = str(row[fio_idx]).strip() if fio_idx < len(row) and row[fio_idx] else ''
                contact = str(row[contact_idx]).strip() if contact_idx < len(row) and row[contact_idx] else ''
                mobile = str(row[mobile_idx]).strip() if mobile_idx < len(row) and row[mobile_idx] else ''
                city = str(row[city_idx]).strip() if city_idx < len(row) and row[city_idx] else ''
                
                vsp = normalize_vsp_code(vsp)
                
                if vsp and fio:
                    record = {
                        'vsp': vsp,
                        'fio': fio,
                        'contact': contact,
                        'mobile': mobile,
                        'city': city
                    }
                    vsp_map[vsp] = record
                    
                    if city:
                        if city not in city_map:
                            city_map[city] = []
                        city_map[city].append(record)
            else:
                logger.warning(f"Row {i} has insufficient columns: {row}")
        
        logger.info(f"Processed {len(vsp_map)} records from Google Sheets")
        return vsp_map, city_map
        
    except Exception as e:
        logger.error(f"Error loading data from Google Sheets: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def normalize_vsp_code(vsp_raw):
    """Нормализация кода ВСП"""
    if not vsp_raw:
        return ""
    
    # Удаляем лишние пробелы и приводим к верхнему регистру
    vsp = vsp_raw.strip().upper()
    
    # Заменяем различные разделители на стандартный слеш
    vsp = vsp.replace(' ', '/').replace('\\', '/').replace('|', '/')
    
    return vsp

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
        
        return {
            "success": True,
            "spreadsheet_title": title,
            "spreadsheet_url": url,
            "sheet_title": sheet.title
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

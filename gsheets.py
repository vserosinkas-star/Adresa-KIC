import os
import logging
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# === Мок-данные (если Google Sheets недоступен) ===
MOCK_DATA = {
    "Ямбург": [
        {
            "location": "Ямбург",
            "kic": "ДО №8369/018 КИЦ Новоуренгойский",
            "address": "629300, г. Новый Уренгой, мкр. Дружба, 3",
            "fio": "Мохначёв Сергей Вячеславович",
            "phone": "929-252-0303",
            "email": "Mokhnachov.S.V@sberbank.ru"
        }
    ],
    "Салехард": [
        {
            "location": "Салехард",
            "kic": "ДО №8369/086 КИЦ Салехардский",
            "address": "629007, г. Салехард, ул. Республики, 41",
            "fio": "Криворотко Маргарита Игоревна",
            "phone": "919-557-7799",
            "email": "mikrivorotko@sberbank.ru"
        }
    ]
}


def init_gsheets():
    """Инициализация клиента Google Sheets"""
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if not creds_json:
        logger.error("GOOGLE_CREDENTIALS not set")
        return None

    try:
        creds = Credentials.from_service_account_info(
            eval(creds_json),
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        return build('sheets', 'v4', credentials=creds)
    except Exception as e:
        logger.error(f"Error initializing Google Sheets: {e}")
        return None


def load_data_from_sheets():
    """Загрузка данных из Google Sheets → возвращает (None, location_map)"""
    try:
        client = init_gsheets()
        if not client:
            return None

        SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
        if not SPREADSHEET_ID:
            logger.error("SPREADSHEET_ID not set")
            return None

        sheet = client.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range="Общий"
        ).execute()

        values = result.get('values', [])
        if not values or len(values) < 2:
            logger.warning("No data in sheet")
            return None

        headers = values[0]
        required = ["Населенный пункт", "КИЦ", "Адрес КИЦ", "ФИО РКИЦ", "Телефон РКИЦ", "Email РКИЦ"]
        for col in required:
            if col not in headers:
                logger.error(f"Missing column: {col}")
                return None

        # Индексы
        loc_idx = headers.index("Населенный пункт")
        kic_idx = headers.index("КИЦ")
        addr_idx = headers.index("Адрес КИЦ")
        fio_idx = headers.index("ФИО РКИЦ")
        phone_idx = headers.index("Телефон РКИЦ")
        email_idx = headers.index("Email РКИЦ")

        location_map = {}
        for row in values[1:]:
            try:
                location = row[loc_idx].strip() if loc_idx < len(row) else ""
                if not location:
                    continue

                record = {
                    "location": location,
                    "kic": row[kic_idx].strip() if kic_idx < len(row) else "–",
                    "address": row[addr_idx].strip() if addr_idx < len(row) else "–",
                    "fio": row[fio_idx].strip() if fio_idx < len(row) else "–",
                    "phone": row[phone_idx].strip() if phone_idx < len(row) else "–",
                    "email": row[email_idx].strip() if email_idx < len(row) else "–",
                }

                if location not in location_map:
                    location_map[location] = []
                location_map[location].append(record)

            except Exception as e:
                logger.warning(f"Error parsing row: {row} → {e}")
                continue

        logger.info(f"Parsed {len(location_map)} locations, {sum(len(v) for v in location_map.values())} records")
        return (None, location_map)

    except Exception as e:
        logger.error(f"Exception in load_data_from_sheets: {e}", exc_info=True)
        return None

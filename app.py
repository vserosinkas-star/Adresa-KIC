def load_data_from_sheets():
    """Пытается загрузить данные из Google Sheets"""
    try:
        # Проверяем наличие сервисного аккаунта
        if not os.environ.get('GOOGLE_SERVICE_ACCOUNT'):
            print("GOOGLE_SERVICE_ACCOUNT не найден, использую тестовые данные")
            return None
        
        # Загружаем сервисный аккаунт
        service_account_info = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT'))
        
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_info(
            service_account_info, 
            scopes=scopes
        )
        
        client = gspread.authorize(credentials)
        
        # Открываем таблицу
        spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
        worksheet = spreadsheet.get_worksheet(0)
        
        # Получаем все данные
        all_values = worksheet.get_all_values()
        
        print(f"Загружено строк из Google Sheets: {len(all_values)}")
        if len(all_values) > 0:
            print(f"Первая строка (заголовки): {all_values[0]}")
        if len(all_values) > 1:
            print(f"Вторая строка (первая запись): {all_values[1]}")
        
        if len(all_values) <= 1:
            print("Таблица пуста или содержит только заголовки")
            return None
        
        # Парсим данные
        data_dict = {}
        for row in all_values[1:]:  # Пропускаем заголовки
            if len(row) > 0 and row[0].strip():
                kic_code = row[0].strip()
                key = re.sub(r'[^\w]', '', kic_code.upper())
                
                entry = {"kic": kic_code}
                if len(row) > 1: entry["city"] = row[1].strip()
                if len(row) > 2: entry["address"] = row[2].strip()
                if len(row) > 3: entry["fio"] = row[3].strip()
                if len(row) > 4: entry["phone"] = row[4].strip()
                if len(row) > 5: entry["email"] = row[5].strip()
                
                data_dict[key] = entry
        
        print(f"✅ Загружено {len(data_dict)} записей из Google Sheets")
        return data_dict
        
    except Exception as e:
        print(f"❌ Ошибка загрузки из Google Sheets: {e}")
        import traceback
        traceback.print_exc()
        return None

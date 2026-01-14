import requests
import json
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import time


API_BASE_URL = "https://apidata.mos.ru/v1"
DATASET_ID = 586
API_KEY = "8b66460e-5b86-4ffe-9d2e-6b4664b60e15"  
BATCH_SIZE = 1000 


DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "database": "romanlin$default",  
    "user": "root",
    "password": "", 
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci",
}


def get_db_connection():
    """Создать подключение к БД"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"Ошибка подключения к БД: {e}")
        return None


def get_or_create_adm_area(cursor, name):
    """Получить или создать административный округ"""
    if not name:
        return None

    cursor.execute("SELECT id FROM adm_areas WHERE name = %s", (name,))
    result = cursor.fetchone()

    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO adm_areas (name) VALUES (%s)", (name,))
        return cursor.lastrowid


def get_or_create_district(cursor, adm_area_id, name):
    """Получить или создать район"""
    if not name or not adm_area_id:
        return None

    cursor.execute(
        "SELECT id FROM districts WHERE adm_area_id = %s AND name = %s",
        (adm_area_id, name),
    )
    result = cursor.fetchone()

    if result:
        return result[0]
    else:
        cursor.execute(
            "INSERT INTO districts (adm_area_id, name) VALUES (%s, %s)",
            (adm_area_id, name),
        )
        return cursor.lastrowid


def get_or_create_license_type(cursor, code):
    """Получить ID типа лицензии по коду"""
    if not code:
        return None

    cursor.execute("SELECT id FROM license_types WHERE code = %s", (code,))
    result = cursor.fetchone()

    if result:
        return result[0]
    return None


def get_or_create_license_status(cursor, status):
    """Получить или создать статус лицензии"""
    if not status:
        return None

    cursor.execute("SELECT id FROM license_statuses WHERE status = %s", (status,))
    result = cursor.fetchone()

    if result:
        return result[0]
    else:
        cursor.execute(
            "INSERT INTO license_statuses (status) VALUES (%s)",
            (status,),
        )
        return cursor.lastrowid


def normalize_text(value):
    """
    Преобразовать сложные типы (списки и т.п.) в строку,
    чтобы избежать ошибки "Python 'list' cannot be converted to a MySQL type".
    """
    if isinstance(value, (list, tuple, set)):
        return ", ".join(map(str, value))
    return value


def extract_coordinates(geo_data):
    """Извлечь координаты из geoData или geodata_center"""
    if not geo_data:
        return None, None

    # Если это словарь с coordinates
    if isinstance(geo_data, dict):
        coords = geo_data.get("coordinates", [])
        if isinstance(coords, list) and len(coords) >= 2:
            return float(coords[0]), float(coords[1])  # longitude, latitude

    # Если это список напрямую
    if isinstance(geo_data, list) and len(geo_data) >= 2:
        return float(geo_data[0]), float(geo_data[1])

    return None, None


def parse_date(date_str):
    """Парсинг даты из строки"""
    if not date_str:
        return None

    try:
        # Формат: "19.03.2018"
        if "." in date_str:
            return datetime.strptime(date_str, "%d.%m.%Y").date()
        # Другие форматы можно добавить
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None


def fetch_data_from_api(skip=0, top=1000):
    """Получить данные из API"""
    url = f"{API_BASE_URL}/datasets/{DATASET_ID}/rows?$skip={skip}&$top={top}&api_key={API_KEY}"

    # Используем сессию и отключаем системные прокси, чтобы они не мешали запросам
    session = requests.Session()
    session.trust_env = False

    try:
        response = session.get(
            url,
            timeout=60,  
            verify=False,
            proxies={"http": None, "https": None},
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Ошибка API: статус {response.status_code}")
            print(f"Ответ: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"Ошибка запроса к API: {e}")
        return None


def process_company(cursor, record):
    """Обработка одной записи компании с фильтрацией актуальных версий"""
    try:
        cells = record.get("Cells", {})

        # Основные поля
        global_id = record.get("global_id")
        dataset_row_id = record.get("dataset_row_id")
        object_name_on_doc = normalize_text(cells.get("ObjectNameOnDoc"))
        object_name = normalize_text(cells.get("ObjectName"))
        address = normalize_text(cells.get("Address"))
        adm_area_name = normalize_text(cells.get("AdmArea"))
        district_name = normalize_text(cells.get("District"))
        subject_name = normalize_text(cells.get("SubjectName"))
        legal_address = normalize_text(cells.get("LegalAddress"))
        email = normalize_text(cells.get("Email"))
        inn = normalize_text(cells.get("INN"))
        kpp = normalize_text(cells.get("KPP"))
        kpp_separate = normalize_text(cells.get("KPPSeparateDivision"))

        # Лицензия
        job_type_code = normalize_text(cells.get("JobTypeCode"))
        license_number = normalize_text(cells.get("LicenseNumber"))
        license_number_registry = normalize_text(cells.get("LicenseNumberInRegistry"))
        license_begin = parse_date(cells.get("LicenseBegin"))
        license_expire = parse_date(cells.get("LicenseExpire"))
        install_date = parse_date(cells.get("InstallDateOfCurrentLicenseState"))
        date_of_decision = parse_date(cells.get("DateOfDecision"))
        license_status = normalize_text(cells.get("CurrentLicenseState"))
        licensing_authority = normalize_text(cells.get("NameOfLicensingAuthority"))

        # Дополнительная информация
        n_fias = normalize_text(cells.get("N_FIAS"))
        cadastral_number = normalize_text(cells.get("CadastralNumber"))

        # Геоданные
        geo_data = cells.get("geoData")
        geo_data_center = cells.get("geodata_center")

        # Извлечение координат (приоритет geoData, потом geodata_center)
        longitude, latitude = extract_coordinates(geo_data) or extract_coordinates(
            geo_data_center
        )

        # ПРОВЕРКА: Пропускаем записи без координат
        if not longitude or not latitude:
            return False

        # ПРОВЕРКА: Фильтрация актуальных записей по ИНН или адресу
        if inn and inn.strip():
            # Проверяем, есть ли уже более свежая запись для этого ИНН
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM companies 
                WHERE inn = %s 
                AND (
                    install_date_of_current_state > %s 
                    OR (install_date_of_current_state = %s AND license_expire > %s)
                )
            """, (inn, install_date or '1900-01-01', install_date or '1900-01-01', license_expire or '1900-01-01'))
            
            result = cursor.fetchone()
            if result and result['count'] > 0:
                # Есть более свежая запись, пропускаем эту
                return False
        else:
            # Если нет ИНН, группируем по адресу
            if address and address.strip():
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM companies 
                    WHERE inn IS NULL OR inn = '' 
                    AND address = %s 
                    AND (
                        install_date_of_current_state > %s 
                        OR (install_date_of_current_state = %s AND license_expire > %s)
                    )
                """, (address, install_date or '1900-01-01', install_date or '1900-01-01', license_expire or '1900-01-01'))
                
                result = cursor.fetchone()
                if result and result['count'] > 0:
                    # Есть более свежая запись, пропускаем эту
                    return False

        # Нормализация данных
        adm_area_id = (
            get_or_create_adm_area(cursor, adm_area_name) if adm_area_name else None
        )
        district_id = (
            get_or_create_district(cursor, adm_area_id, district_name)
            if district_name
            else None
        )
        license_type_id = (
            get_or_create_license_type(cursor, job_type_code) if job_type_code else None
        )
        license_status_id = (
            get_or_create_license_status(cursor, license_status) if license_status else None
        )

        # Подготовка JSON для геоданных
        geo_data_json = json.dumps(geo_data) if geo_data else None
        geo_data_center_json = json.dumps(geo_data_center) if geo_data_center else None

        # Вставка или обновление записи
        sql = """
        INSERT INTO companies (
            global_id, dataset_row_id, object_name_on_doc, object_name, address,
            adm_area_id, district_id, subject_name, legal_address, email,
            inn, kpp, kpp_separate_division, license_type_id, license_number,
            license_number_in_registry, license_begin, license_expire,
            install_date_of_current_state, date_of_decision, license_status_id,
            licensing_authority, n_fias, cadastral_number,
            longitude, latitude, geo_data_json, geo_data_center_json
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON DUPLICATE KEY UPDATE
            object_name_on_doc = VALUES(object_name_on_doc),
            object_name = VALUES(object_name),
            address = VALUES(address),
            adm_area_id = VALUES(adm_area_id),
            district_id = VALUES(district_id),
            subject_name = VALUES(subject_name),
            legal_address = VALUES(legal_address),
            email = VALUES(email),
            inn = VALUES(inn),
            kpp = VALUES(kpp),
            kpp_separate_division = VALUES(kpp_separate_division),
            license_type_id = VALUES(license_type_id),
            license_number = VALUES(license_number),
            license_number_in_registry = VALUES(license_number_in_registry),
            license_begin = VALUES(license_begin),
            license_expire = VALUES(license_expire),
            install_date_of_current_state = VALUES(install_date_of_current_state),
            date_of_decision = VALUES(date_of_decision),
            license_status_id = VALUES(license_status_id),
            licensing_authority = VALUES(licensing_authority),
            n_fias = VALUES(n_fias),
            cadastral_number = VALUES(cadastral_number),
            longitude = VALUES(longitude),
            latitude = VALUES(latitude),
            geo_data_json = VALUES(geo_data_json),
            geo_data_center_json = VALUES(geo_data_center_json),
            updated_at = CURRENT_TIMESTAMP
        """

        values = (
            global_id,
            record.get("global_id"),
            object_name_on_doc,
            object_name,
            address,
            adm_area_id,
            district_id,
            subject_name,
            legal_address,
            email,
            inn,
            kpp,
            kpp_separate,
            license_type_id,
            license_number,
            license_number_registry,
            license_begin,
            license_expire,
            install_date,
            date_of_decision,
            license_status_id,
            licensing_authority,
            n_fias,
            cadastral_number,
            longitude,
            latitude,
            geo_data_json,
            geo_data_center_json,
        )

        cursor.execute(sql, values)
        return True

    except Exception as e:
        print(f"   ⚠ Ошибка при обработке записи: {e}")
        return False


def load_all_data():
    """Загрузить все данные из API в БД"""
    print("=" * 60)
    print("ЗАГРУЗКА ДАННЫХ ИЗ API В БАЗУ ДАННЫХ (ЛОКАЛЬНО)")
    print("=" * 60)

    # Подключение к БД
    connection = get_db_connection()
    if not connection:
        print("Не удалось подключиться к БД!")
        return

    cursor = connection.cursor()

    # Получить общее количество записей
    print("\n1. Получение количества записей...")
    try:
        url = f"{API_BASE_URL}/datasets/{DATASET_ID}/count?api_key={API_KEY}"
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            url,
            timeout=60,
            verify=False,
            proxies={"http": None, "https": None},
        )
        if response.status_code == 200:
            total_count = int(response.text.strip('"'))
            print(f"   ✓ Всего записей в датасете: {total_count}")
        else:
            print(f"   ⚠ Не удалось получить количество, продолжаем...")
            total_count = None
    except Exception as e:
        print(f"   ⚠ Ошибка: {e}")
        total_count = None

    # Загрузка данных по частям
    print("\n2. Загрузка данных...")
    skip = 0
    loaded = 0
    errors = 0
    start_time = time.time()

    while True:
        print(f"\n   Загрузка записей {skip} - {skip + BATCH_SIZE}...")

        # Получить данные из API
        data = fetch_data_from_api(skip, BATCH_SIZE)

        if not data or len(data) == 0:
            print("   Нет данных, завершение загрузки.")
            break

        # Обработать каждую запись
        batch_loaded = 0
        for record in data:
            if process_company(cursor, record):
                batch_loaded += 1
                loaded += 1
            else:
                errors += 1

        # Коммит батча
        connection.commit()

        print(f"   ✓ Загружено: {batch_loaded} записей (всего: {loaded})")

        # Если получили меньше записей, чем запрашивали - это последний батч
        if len(data) < BATCH_SIZE:
            print("   Достигнут конец данных.")
            break

        skip += BATCH_SIZE
        time.sleep(0.3)  # небольшая пауза, чтобы не спамить API

    elapsed_time = time.time() - start_time

    # Итоговая статистика
    print("\n" + "=" * 60)
    print("ЗАГРУЗКА ЗАВЕРШЕНА")
    print("=" * 60)
    print(f"Загружено записей: {loaded}")
    print(f"Ошибок: {errors}")
    print(f"Время выполнения: {elapsed_time:.2f} секунд")

    if total_count:
        print(f"Ожидалось записей: {total_count}")
        if loaded < total_count:
            print("⚠ Загружено меньше, чем ожидалось. Возможно, некоторые записи пропущены.")

    cursor.close()
    connection.close()
    print("\n✓ Готово!")


if __name__ == "__main__":
    load_all_data()
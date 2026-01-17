from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import logging
import os
import schedule
import time
import threading
import random

# Импорт модуля аутентификации
try:
    from auth import AuthManager
    AUTH_AVAILABLE = True
except ImportError as e:
    AUTH_AVAILABLE = False
    print(f"Модуль аутентификации недоступен: {e}")
    logging.warning(f"Функции аутентификации отключены: {e}")

# Импорт модуля обновления данных
try:
    from load_data_local import load_all_data
    DATA_LOADER_AVAILABLE = True
except ImportError as e:
    DATA_LOADER_AVAILABLE = False
    print(f"Модуль загрузки данных недоступен: {e}")
    logging.warning(f"Планировщик задач недоступен: {e}. Автоматическое обновление отключено.")


def run_scheduler():
    """Запуск планировщика в отдельном потоке"""
    if DATA_LOADER_AVAILABLE:
        # Планируем загрузку данных каждую неделю (каждый понедельник в 3:00)
        schedule.every().monday.at("03:00").do(run_scheduled_update)
        
        print("Планировщик запущен. Автоматическая загрузка данных каждую неделю в понедельник в 3:00.")
        
        while True:
            schedule.run_pending()
            time.sleep(3600)  # Проверяем каждый час

def run_scheduled_update():
    """Запуск планового обновления данных"""
    try:
        print("=" * 60)
        print("ЗАПУСК ПЛАНОВОГО ОБНОВЛЕНИЯ ДАННЫХ")
        print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        load_all_data()
        
        print("=" * 60)
        print("ПЛАНОВОЕ ОБНОВЛЕНИЕ ЗАВЕРШЕНО")
        print("=" * 60)
        
    except Exception as e:
        print(f"Ошибка при плановом обновлении: {e}")
        logging.error(f"Ошибка при плановом обновлении данных: {e}")

def create_app():
    app = Flask(__name__)
    CORS(app)

    # Локальное подключение к MySQL (XAMPP)
    app.config["DB_CONFIG"] = {
        "host": "127.0.0.1",  # Используем IP вместо localhost для избежания проблем с IPv6
        "port": 3306,
        "database": "romanlin$default",  # Рабочая база данных
        "user": "root",
        "password": "",
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        "connection_timeout": 5,  # Таймаут подключения 5 секунд
    }

    # Инициализация менеджера аутентификации
    auth_manager = None
    if AUTH_AVAILABLE:
        try:
            auth_manager = AuthManager(app.config["DB_CONFIG"])
            app.config["AUTH_MANAGER"] = auth_manager
            print("Менеджер аутентификации успешно инициализирован")
        except Exception as e:
            print(f"Ошибка инициализации аутентификации: {e}")
            app.config["AUTH_MANAGER"] = None

    def get_db_connection():
        try:
            conn = mysql.connector.connect(**app.config["DB_CONFIG"])
            return conn
        except Error as e:
            print(f"Ошибка подключения к БД: {e}")
            import traceback
            traceback.print_exc()
            return None
        except Exception as e:
            print(f"Неожиданная ошибка при подключении к БД: {e}")
            import traceback
            traceback.print_exc()
            return None

    @app.route("/api/health")
    def health():
        """Проверка, что backend жив и БД доступна."""
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "error", "db": "unavailable"}), 500
        conn.close()
        return jsonify({"status": "ok", "db": "ok"})

    # Кэш для версии БД (чтобы не проверять каждый раз)
    _db_version_cache = None
    
    def get_latest_companies_query():
        """
        Возвращает SQL запрос для получения только актуальных записей предприятий.
        Использует ROW_NUMBER() для MySQL 8.0+ / MariaDB 10.2+ или альтернативный подход для старых версий.
        """
        global _db_version_cache
        
        # Проверяем версию MySQL/MariaDB (кэшируем результат)
        if _db_version_cache is None:
            try:
                test_conn = get_db_connection()
                if test_conn:
                    test_cursor = test_conn.cursor()
                    test_cursor.execute("SELECT VERSION() as version")
                    version_str = test_cursor.fetchone()[0]
                    # Извлекаем основную версию (например, "10.4.32" -> 10.4)
                    version_parts = version_str.split('-')[0].split('.')
                    version_major = float(version_parts[0])
                    version_minor = float(version_parts[1]) if len(version_parts) > 1 else 0
                    _db_version_cache = (version_major, version_minor)
                    print(f"Определена версия БД: {version_major}.{int(version_minor)}")
                    test_cursor.close()
                    test_conn.close()
                else:
                    _db_version_cache = (0, 0)  # Не удалось подключиться
            except Exception as e:
                print(f"Ошибка при определении версии БД: {e}")
                _db_version_cache = (0, 0)
        
        version_major, version_minor = _db_version_cache
        
        # MySQL 8.0+ или MariaDB 10.2+ поддерживают ROW_NUMBER()
        if (version_major > 8) or (version_major == 8 and version_minor >= 0) or (version_major == 10 and version_minor >= 2):
            # MySQL 8.0+ поддерживает ROW_NUMBER()
            return """
                SELECT 
                    cf.id,
                    cf.object_name,
                    cf.address,
                    cf.adm_area,
                    cf.district,
                    cf.license_type_code,
                    cf.license_type_name,
                    cf.license_number,
                    cf.license_begin,
                    cf.license_expire,
                    cf.license_status,
                    cf.license_status_color,
                    cf.longitude,
                    cf.latitude,
                    cf.inn,
                    cf.kpp,
                    cf.subject_name
                FROM companies_full cf
                INNER JOIN (
                    SELECT 
                        c.id,
                        ROW_NUMBER() OVER (
                            PARTITION BY 
                                CASE 
                                    WHEN c.inn IS NOT NULL AND c.inn != '' THEN c.inn
                                    ELSE CONCAT('ADDR_', c.address)
                                END
                            ORDER BY 
                                COALESCE(c.install_date_of_current_state, '1900-01-01') DESC,
                                COALESCE(c.license_expire, '1900-01-01') DESC,
                                c.updated_at DESC,
                                c.id DESC
                        ) as rn
                    FROM companies c
                    WHERE c.longitude IS NOT NULL 
                        AND c.latitude IS NOT NULL
                ) latest ON cf.id = latest.id AND latest.rn = 1
                WHERE cf.longitude IS NOT NULL
                AND cf.latitude IS NOT NULL
            """
        
        # Альтернативный подход для старых версий MySQL (используем подзапрос с MAX)
        return """
            SELECT 
                cf.id,
                cf.object_name,
                cf.address,
                cf.adm_area,
                cf.district,
                cf.license_type_code,
                cf.license_type_name,
                cf.license_number,
                cf.license_begin,
                cf.license_expire,
                cf.license_status,
                cf.license_status_color,
                cf.longitude,
                cf.latitude,
                cf.inn,
                cf.kpp,
                cf.subject_name
            FROM companies_full cf
            INNER JOIN (
                SELECT 
                    c1.id
                FROM companies c1
                INNER JOIN (
                    SELECT 
                        CASE 
                            WHEN c2.inn IS NOT NULL AND c2.inn != '' THEN c2.inn
                            ELSE CONCAT('ADDR_', c2.address)
                        END as company_key,
                        MAX(COALESCE(c2.install_date_of_current_state, '1900-01-01')) as max_install_date,
                        MAX(COALESCE(c2.license_expire, '1900-01-01')) as max_expire_date,
                        MAX(c2.updated_at) as max_updated_at,
                        MAX(c2.id) as max_id
                    FROM companies c2
                    WHERE c2.longitude IS NOT NULL 
                        AND c2.latitude IS NOT NULL
                    GROUP BY company_key
                ) latest ON 
                    (CASE 
                        WHEN c1.inn IS NOT NULL AND c1.inn != '' THEN c1.inn
                        ELSE CONCAT('ADDR_', c1.address)
                    END) = latest.company_key
                    AND COALESCE(c1.install_date_of_current_state, '1900-01-01') = latest.max_install_date
                    AND COALESCE(c1.license_expire, '1900-01-01') = latest.max_expire_date
                    AND c1.updated_at = latest.max_updated_at
                    AND c1.id = latest.max_id
                WHERE c1.longitude IS NOT NULL 
                    AND c1.latitude IS NOT NULL
            ) latest_ids ON cf.id = latest_ids.id
            WHERE cf.longitude IS NOT NULL
            AND cf.latitude IS NOT NULL
        """

    @app.route("/api/companies")
    def get_companies():
        """
        Получить список компаний с фильтрацией.
        Фильтры (query parameters):
        - limit: количество записей (макс. 1000)
        - load_all: true/false - загружать все в bounds без лимита
        - bounds: "south,west,north,east" - границы видимой области
        - zoom_level: текущий масштаб
        - status_color: active | expiring_soon | expired
        - adm_area: название административного округа
        - district: название района
        - license_type: РАО | РПО | РПА
        - search: поиск по названию, адресу, ИНН, КПП
        """
        limit = min(int(request.args.get("limit", 200)), 1000)
        load_all = request.args.get("load_all", "false").lower() == "true"
        bounds = request.args.get("bounds")
        zoom_level = request.args.get("zoom_level")
        status_color = request.args.get("status_color")
        adm_area = request.args.get("adm_area")
        district = request.args.get("district")
        license_type = request.args.get("license_type")
        search = request.args.get("search")

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "DB connection failed"}), 500

        cursor = conn.cursor(dictionary=True)

        try:
            # ПРОСТОЙ ЗАПРОС БЕЗ ФИЛЬТРАЦИИ ДУБЛИКАТОВ (теперь load_data_local фильтрует при загрузке)
            base_sql = """
                SELECT 
                    c.id,
                    c.object_name,
                    c.address,
                    aa.name as adm_area,
                    d.name as district,
                    lt.code as license_type_code,
                    lt.name as license_type_name,
                    c.license_number,
                    c.license_begin,
                    c.license_expire,
                    ls.status as license_status,
                    CASE 
                        WHEN c.license_expire IS NULL THEN 'expired'
                        WHEN c.license_expire < CURDATE() THEN 'expired'
                        WHEN c.license_expire <= DATE_ADD(CURDATE(), INTERVAL 30 DAY) THEN 'expiring_soon'
                        ELSE 'active'
                    END as license_status_color,
                    c.longitude,
                    c.latitude,
                    c.inn,
                    c.kpp,
                    c.subject_name
                FROM companies c
                LEFT JOIN adm_areas aa ON c.adm_area_id = aa.id
                LEFT JOIN districts d ON c.district_id = d.id
                LEFT JOIN license_types lt ON c.license_type_id = lt.id
                LEFT JOIN license_statuses ls ON c.license_status_id = ls.id
                WHERE c.longitude IS NOT NULL
                AND c.latitude IS NOT NULL
            """
            
            conditions = []
            params = []
            
            # Добавляем фильтрацию по bounds если load_all=true
            if load_all and bounds:
                try:
                    south, west, north, east = map(float, bounds.split(','))
                    conditions.append("""
                        c.latitude BETWEEN %s AND %s
                        AND c.longitude BETWEEN %s AND %s
                    """)
                    params.extend([south, north, west, east])
                except (ValueError, IndexError):
                    print(f"Неверный формат bounds: {bounds}")
            
            if status_color:
                conditions.append("""
                    CASE 
                        WHEN c.license_expire IS NULL THEN 'expired'
                        WHEN c.license_expire < CURDATE() THEN 'expired'
                        WHEN c.license_expire <= DATE_ADD(CURDATE(), INTERVAL 30 DAY) THEN 'expiring_soon'
                        ELSE 'active'
                    END = %s
                """)
                params.append(status_color)
            
            if adm_area:
                conditions.append("aa.name = %s")
                params.append(adm_area)
            
            if district:
                conditions.append("d.name = %s")
                params.append(district)
            
            if license_type:
                conditions.append("lt.code = %s")
                params.append(license_type)
            
            if search:
                conditions.append("""
                    (c.object_name LIKE %s 
                    OR c.address LIKE %s 
                    OR c.subject_name LIKE %s
                    OR c.inn LIKE %s)
                """)
                search_term = f"%{search}%"
                params.extend([search_term, search_term, search_term, search_term])
            
            # Добавляем условия к запросу
            if conditions:
                base_sql += " AND " + " AND ".join(conditions)
            
            # Сортировка и лимит
            base_sql += " ORDER BY c.id"
            
            # Добавляем лимит только если не load_all
            if not load_all:
                base_sql += " LIMIT %s"
                params.append(limit)
            
            cursor.execute(base_sql, params)
            rows = cursor.fetchall()
            
        except Error as e:
            conn.close()
            print(f"Ошибка SQL при получении компаний: {e}")
            return jsonify({"error": str(e)}), 500
        except Exception as e:
            conn.close()
            print(f"Неожиданная ошибка при получении компаний: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

        conn.close()
        return jsonify(rows)

    @app.route("/api/filters/options")
    def get_filter_options():
        """Получить доступные опции для фильтров"""
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "DB connection failed"}), 500

        cursor = conn.cursor(dictionary=True)

        try:
            # Получаем округа
            cursor.execute("SELECT DISTINCT name FROM adm_areas ORDER BY name")
            adm_areas = [row['name'] for row in cursor.fetchall()]
            
            # Получаем районы
            cursor.execute("SELECT DISTINCT d.name FROM districts d ORDER BY d.name")
            districts = [row['name'] for row in cursor.fetchall()]
            
            # Получаем типы лицензий
            cursor.execute("SELECT code, name FROM license_types ORDER BY code")
            license_types = cursor.fetchall()
            
            conn.close()
            return jsonify({
                "adm_areas": adm_areas,
                "districts": districts,
                "license_types": license_types
            })
        except Error as e:
            conn.close()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/search/autocomplete")
    def autocomplete_search():
        """
        Автодополнение для поиска:
        - query: поисковый запрос
        - limit: количество результатов (по умолчанию 10)
        """
        query = request.args.get("query", "").strip()
        limit = min(int(request.args.get("limit", 10)), 50)
        
        if not query or len(query) < 2:
            return jsonify([])
        
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "DB connection failed"}), 500

        cursor = conn.cursor(dictionary=True)
        search_term = f"%{query}%"

        try:
            # Используем тот же подход для фильтрации дубликатов
            base_autocomplete_sql = get_latest_companies_query()
            sql = base_autocomplete_sql + """
                AND (cf.object_name LIKE %s 
                    OR cf.address LIKE %s 
                    OR cf.subject_name LIKE %s
                    OR cf.inn LIKE %s)
                LIMIT %s
            """
            cursor.execute(sql, [search_term, search_term, search_term, search_term, limit])
            results = cursor.fetchall()
            
            conn.close()
            return jsonify(results)
        except Error as e:
            conn.close()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/update-data", methods=["POST"])
    def manual_update():
        """
        Ручной запуск обновления данных из API.
        Полезно для тестирования или принудительного обновления.
        """
        if not DATA_LOADER_AVAILABLE:
            return jsonify({
                "status": "error",
                "message": "Модуль загрузки данных недоступен"
            }), 500
            
        try:
            load_all_data()
            return jsonify({
                "status": "success",
                "message": "Данные успешно обновлены"
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Ошибка при обновлении данных: {str(e)}"
            }), 500

    # Эндпоинты для управления избранными предприятиями
    @app.route("/api/favorites", methods=["GET"])
    def get_favorites():
        """Получить список избранных предприятий текущего пользователя"""
        if not app.config.get("AUTH_MANAGER"):
            return jsonify({"error": "Сервис аутентификации недоступен"}), 503
        
        try:
            session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not session_token:
                return jsonify({"error": "Отсутствует токен авторизации"}), 401
            
            # Валидация сессии
            auth_result = app.config["AUTH_MANAGER"].validate_session(session_token)
            if not auth_result["valid"]:
                return jsonify({"error": "Недействительная сессия"}), 401
            
            user_id = auth_result["user"]["id"]
            conn = get_db_connection()
            if not conn:
                return jsonify({"error": "Ошибка подключения к базе данных"}), 500
            
            cursor = conn.cursor(dictionary=True)
            
            # Получаем избранные предприятия с полной информацией
            query = """
            SELECT 
                uf.id as favorite_id,
                uf.company_id,
                uf.company_name,
                uf.company_address,
                uf.added_at,
                c.object_name,
                c.address,
                c.longitude,
                c.latitude,
                c.license_number,
                c.license_expire,
                lt.code as license_type_code,
                lt.name as license_type_name,
                ls.status as license_status,
                aa.name as adm_area,
                d.name as district,
                DATEDIFF(c.license_expire, CURDATE()) as days_until_expire,
                CASE 
                    WHEN c.license_expire < CURDATE() THEN 'expired'
                    WHEN DATEDIFF(c.license_expire, CURDATE()) <= 30 THEN 'expiring_soon'
                    ELSE 'active'
                END as license_status_color
            FROM user_favorites uf
            LEFT JOIN companies c ON uf.company_id = c.id
            LEFT JOIN license_types lt ON c.license_type_id = lt.id
            LEFT JOIN license_statuses ls ON c.license_status_id = ls.id
            LEFT JOIN adm_areas aa ON c.adm_area_id = aa.id
            LEFT JOIN districts d ON c.district_id = d.id
            WHERE uf.user_id = %s
            ORDER BY uf.added_at DESC
            """
            
            cursor.execute(query, (user_id,))
            favorites = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return jsonify({
                "success": True,
                "favorites": favorites
            }), 200
            
        except Exception as e:
            print(f"Ошибка при получении избранных: {e}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500

    @app.route("/api/favorites", methods=["POST"])
    def add_favorite():
        """Добавить предприятие в избранное"""
        if not app.config.get("AUTH_MANAGER"):
            return jsonify({"error": "Сервис аутентификации недоступен"}), 503
        
        try:
            session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not session_token:
                return jsonify({"error": "Отсутствует токен авторизации"}), 401
            
            # Валидация сессии
            auth_result = app.config["AUTH_MANAGER"].validate_session(session_token)
            if not auth_result["valid"]:
                return jsonify({"error": "Недействительная сессия"}), 401
            
            user_id = auth_result["user"]["id"]
            data = request.get_json()
            
            if not data or "company_id" not in data:
                return jsonify({"error": "Отсутствует ID предприятия"}), 400
            
            company_id = data["company_id"]
            
            conn = get_db_connection()
            if not conn:
                return jsonify({"error": "Ошибка подключения к базе данных"}), 500
            
            cursor = conn.cursor(dictionary=True)
            
            # Проверяем существование предприятия
            cursor.execute("SELECT id, object_name, address FROM companies WHERE id = %s", (company_id,))
            company = cursor.fetchone()
            
            if not company:
                cursor.close()
                conn.close()
                return jsonify({"error": "Предприятие не найдено"}), 404
            
            # Проверяем, не добавлено ли уже в избранное
            cursor.execute(
                "SELECT id FROM user_favorites WHERE user_id = %s AND company_id = %s",
                (user_id, company_id)
            )
            existing = cursor.fetchone()
            
            if existing:
                cursor.close()
                conn.close()
                return jsonify({"error": "Предприятие уже в избранном"}), 409
            
            # Добавляем в избранное
            insert_query = """
            INSERT INTO user_favorites (user_id, company_id, company_name, company_address)
            VALUES (%s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                user_id, 
                company_id, 
                company["object_name"], 
                company["address"]
            ))
            
            conn.commit()
            favorite_id = cursor.lastrowid
            
            cursor.close()
            conn.close()
            
            return jsonify({
                "success": True,
                "message": "Предприятие добавлено в избранное",
                "favorite_id": favorite_id
            }), 201
            
        except Exception as e:
            print(f"Ошибка при добавлении в избранное: {e}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500

    @app.route("/api/favorites/<int:company_id>", methods=["DELETE"])
    def remove_favorite(company_id):
        """Удалить предприятие из избранного"""
        if not app.config.get("AUTH_MANAGER"):
            return jsonify({"error": "Сервис аутентификации недоступен"}), 503
        
        try:
            session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not session_token:
                return jsonify({"error": "Отсутствует токен авторизации"}), 401
            
            # Валидация сессии
            auth_result = app.config["AUTH_MANAGER"].validate_session(session_token)
            if not auth_result["valid"]:
                return jsonify({"error": "Недействительная сессия"}), 401
            
            user_id = auth_result["user"]["id"]
            
            conn = get_db_connection()
            if not conn:
                return jsonify({"error": "Ошибка подключения к базе данных"}), 500
            
            cursor = conn.cursor()
            
            # Удаляем из избранного
            delete_query = "DELETE FROM user_favorites WHERE user_id = %s AND company_id = %s"
            cursor.execute(delete_query, (user_id, company_id))
            
            affected_rows = cursor.rowcount
            conn.commit()
            
            cursor.close()
            conn.close()
            
            if affected_rows > 0:
                return jsonify({
                    "success": True,
                    "message": "Предприятие удалено из избранного"
                }), 200
            else:
                return jsonify({"error": "Предприятие не найдено в избранном"}), 404
            
        except Exception as e:
            print(f"Ошибка при удалении из избранного: {e}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500

    @app.route("/api/favorites/check/<int:company_id>", methods=["GET"])
    def check_favorite(company_id):
        """Проверить, находится ли предприятие в избранном"""
        if not app.config.get("AUTH_MANAGER"):
            return jsonify({"error": "Сервис аутентификации недоступен"}), 503
        
        try:
            session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not session_token:
                return jsonify({"is_favorite": False, "error": "Не авторизован"}), 401
            
            # Валидация сессии
            auth_result = app.config["AUTH_MANAGER"].validate_session(session_token)
            if not auth_result["valid"]:
                return jsonify({"is_favorite": False, "error": "Недействительная сессия"}), 401
            
            user_id = auth_result["user"]["id"]
            
            conn = get_db_connection()
            if not conn:
                return jsonify({"error": "Ошибка подключения к базе данных"}), 500
            
            cursor = conn.cursor()
            
            # Проверяем наличие в избранном
            cursor.execute(
                "SELECT id FROM user_favorites WHERE user_id = %s AND company_id = %s",
                (user_id, company_id)
            )
            favorite = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            return jsonify({
                "is_favorite": favorite is not None
            }), 200
            
        except Exception as e:
            print(f"Ошибка при проверке избранного: {e}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500

    # Эндпоинт для k-means кластеризации просроченных лицензий
    @app.route("/api/clustering/expired", methods=["POST"])
    def expired_clustering():
        """Выполнение k-means кластеризации просроченных лицензий"""
        if not app.config.get("AUTH_MANAGER"):
            return jsonify({"error": "Сервис аутентификации недоступен"}), 503
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "Отсутствуют данные"}), 400
            
            k = data.get('k')
            if not k or not isinstance(k, int) or k < 2 or k > 50:
                return jsonify({"error": "Параметр k должен быть целым числом от 2 до 50"}), 400
            
            # Выполняем кластеризацию просроченных лицензий
            auth_manager = app.config["AUTH_MANAGER"]
            conn = auth_manager.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Вызываем процедуру кластеризации просроченных
            cursor.callproc('kmeans_expired_clustering', [k])
            
            # Получаем результаты
            results = cursor.fetchall()
            
            # Получаем границы кластеров для отрисовки
            cursor.execute("""
                SELECT 
                    cluster_id,
                    COUNT(*) as companies_count,
                    MIN(latitude) as min_lat,
                    MAX(latitude) as max_lat,
                    MIN(longitude) as min_lon,
                    MAX(longitude) as max_lon,
                    AVG(latitude) as center_lat,
                    AVG(longitude) as center_lon
                FROM companies 
                WHERE cluster_id IS NOT NULL 
                  AND license_status_id IN (1, 3, 4, 5)
                GROUP BY cluster_id 
                ORDER BY cluster_id
            """)
            
            clusters = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return jsonify({
                "success": True,
                "k": k,
                "clusters": clusters,
                "statistics": results,
                "type": "expired"
            }), 200
            
        except Exception as e:
            print(f"Ошибка при кластеризации просроченных: {e}")
            return jsonify({"error": "Ошибка при выполнении кластеризации просроченных лицензий"}), 500

    # Эндпоинты аутентификации
    @app.route("/api/auth/register", methods=["POST"])
    def register():
        """Регистрация нового пользователя"""
        if not app.config.get("AUTH_MANAGER"):
            return jsonify({"success": False, "message": "Сервис аутентификации недоступен"}), 503
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "Отсутствуют данные"}), 400
            
            email = data.get('email', '').strip()
            password = data.get('password', '')
            first_name = data.get('first_name', '').strip()
            last_name = data.get('last_name', '').strip()
            phone = data.get('phone', '').strip()
            privacy_policy_accepted = bool(data.get('privacy_policy_accepted', False))
            data_processing_consent = bool(data.get('data_processing_consent', False))
            
            # Получение IP и User-Agent
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
            user_agent = request.headers.get('User-Agent', '')
            
            result = app.config["AUTH_MANAGER"].register_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                privacy_policy_accepted=privacy_policy_accepted,
                data_processing_consent=data_processing_consent,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if result["success"]:
                return jsonify(result), 201
            else:
                return jsonify(result), 400
                
        except Exception as e:
            print(f"Ошибка в эндпоинте регистрации: {e}")
            return jsonify({"success": False, "message": "Внутренняя ошибка сервера"}), 500

    @app.route("/api/auth/login", methods=["POST"])
    def login():
        """Вход пользователя"""
        if not app.config.get("AUTH_MANAGER"):
            return jsonify({"success": False, "message": "Сервис аутентификации недоступен"}), 503
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "message": "Отсутствуют данные"}), 400
            
            email = data.get('email', '').strip()
            password = data.get('password', '')
            
            # Получение IP и User-Agent
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
            user_agent = request.headers.get('User-Agent', '')
            
            result = app.config["AUTH_MANAGER"].login_user(
                email=email,
                password=password,
                ip_address=ip_address,
                user_agent=user_agent
            )
            
            if result["success"]:
                return jsonify(result), 200
            else:
                return jsonify(result), 401
                
        except Exception as e:
            print(f"Ошибка в эндпоинте входа: {e}")
            return jsonify({"success": False, "message": "Внутренняя ошибка сервера"}), 500

    @app.route("/api/auth/validate", methods=["POST"])
    def validate_session():
        """Валидация сессии"""
        if not app.config.get("AUTH_MANAGER"):
            return jsonify({"valid": False, "message": "Сервис аутентификации недоступен"}), 503
        
        try:
            data = request.get_json()
            if not data or not data.get('session_token'):
                return jsonify({"valid": False, "message": "Отсутствует токен сессии"}), 400
            
            session_token = data.get('session_token')
            result = app.config["AUTH_MANAGER"].validate_session(session_token)
            
            if result["valid"]:
                return jsonify(result), 200
            else:
                return jsonify(result), 401
                
        except Exception as e:
            print(f"Ошибка в эндпоинте валидации: {e}")
            return jsonify({"valid": False, "message": "Внутренняя ошибка сервера"}), 500

    @app.route("/api/auth/logout", methods=["POST"])
    def logout():
        """Выход пользователя"""
        if not app.config.get("AUTH_MANAGER"):
            return jsonify({"success": False, "message": "Сервис аутентификации недоступен"}), 503
        
        try:
            data = request.get_json()
            if not data or not data.get('session_token'):
                return jsonify({"success": False, "message": "Отсутствует токен сессии"}), 400
            
            session_token = data.get('session_token')
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR'))
            
            result = app.config["AUTH_MANAGER"].logout_user(
                session_token=session_token,
                ip_address=ip_address
            )
            
            if result["success"]:
                return jsonify(result), 200
            else:
                return jsonify(result), 400
                
        except Exception as e:
            print(f"Ошибка в эндпоинте выхода: {e}")
            return jsonify({"success": False, "message": "Внутренняя ошибка сервера"}), 500

    @app.route("/api/auth/user", methods=["GET"])
    def get_user_info():
        """Получение информации о пользователе по токену"""
        if not app.config.get("AUTH_MANAGER"):
            return jsonify({"error": "Сервис аутентификации недоступен"}), 503
        
        try:
            session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not session_token:
                return jsonify({"error": "Отсутствует токен авторизации"}), 401
            
            result = app.config["AUTH_MANAGER"].validate_session(session_token)
            
            if result["valid"]:
                return jsonify({
                    "success": True,
                    "user": result["user"]
                }), 200
            else:
                return jsonify({"error": "Недействительная сессия"}), 401
                
        except Exception as e:
            print(f"Ошибка в эндпоинте получения пользователя: {e}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    
    # Запуск планировщика в отдельном потоке
    if DATA_LOADER_AVAILABLE:
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
    
    app.run(host="0.0.0.0", port=5000, debug=True)
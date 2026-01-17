-- Таблица административных округов
CREATE TABLE IF NOT EXISTS adm_areas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица районов
CREATE TABLE IF NOT EXISTS districts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    adm_area_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (adm_area_id) REFERENCES adm_areas(id) ON DELETE CASCADE,
    UNIQUE KEY unique_district (adm_area_id, name),
    INDEX idx_name (name),
    INDEX idx_adm_area (adm_area_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица типов работ (РАО, РПО, РПА)
CREATE TABLE IF NOT EXISTS license_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(10) NOT NULL UNIQUE COMMENT 'РАО, РПО, РПА',
    name VARCHAR(255) NOT NULL COMMENT 'Полное наименование типа работ',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Заполнение справочника типов работ
INSERT INTO license_types (code, name, description) VALUES
('РАО', 'Розничная продажа алкогольной продукции', 'Полная лицензия на продажу алкоголя'),
('РПО', 'Розничная продажа пива и пивных напитков', 'Лицензия только на пиво'),
('РПА', 'Розничная продажа алкогольной продукции в розлив', 'Лицензия на продажу алкоголя в розлив')
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- Таблица статусов лицензий
CREATE TABLE IF NOT EXISTS license_statuses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    status VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- Основная таблица предприятий
CREATE TABLE IF NOT EXISTS companies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    global_id BIGINT UNIQUE COMMENT 'Глобальный идентификатор из датасета',
    dataset_row_id VARCHAR(36) COMMENT 'ID строки из датасета (GUID)',
    object_name_on_doc VARCHAR(500) COMMENT 'Наименование объекта лицензирования по уставным документам',
    object_name VARCHAR(500) NOT NULL COMMENT 'Наименование объекта лицензирования',
    address VARCHAR(500) NOT NULL COMMENT 'Адрес объекта лицензирования',
    adm_area_id INT COMMENT 'Административный округ',
    district_id INT COMMENT 'Район',
    subject_name VARCHAR(500) COMMENT 'Наименование лицензиата',
    legal_address VARCHAR(500) COMMENT 'Юридический адрес лицензиата',
    email VARCHAR(255) COMMENT 'Адрес электронной почты',
    inn VARCHAR(20) COMMENT 'ИНН лицензиата',
    kpp VARCHAR(20) COMMENT 'КПП лицензиата',
    kpp_separate_division VARCHAR(20) COMMENT 'КПП обособленного подразделения',
    license_type_id INT COMMENT 'Тип работ (РАО, РПО, РПА)',
    license_number VARCHAR(255) COMMENT 'Реквизиты лицензии',
    license_number_in_registry VARCHAR(255) COMMENT 'Номер лицензии в сводном реестре ФСРАР',
    license_begin DATE COMMENT 'Дата начала срока действия лицензии',
    license_expire DATE COMMENT 'Дата окончания срока действия лицензии',
    install_date_of_current_state DATE COMMENT 'Дата установки текущего состояния лицензии',
    date_of_decision DATE COMMENT 'Дата принятия решения',
    license_status_id INT COMMENT 'Текущее состояние лицензии',
    licensing_authority VARCHAR(500) COMMENT 'Наименование органа лицензирования',
    n_fias VARCHAR(36) COMMENT 'Уникальный номер адреса в государственном адресном реестре (UUID)',
    cadastral_number VARCHAR(255) COMMENT 'Кадастровый номер помещения',
    longitude DECIMAL(10, 8) COMMENT 'Долгота (из geoData или geodata_center)',
    latitude DECIMAL(10, 8) COMMENT 'Широта (из geoData или geodata_center)',
    geo_data_json JSON COMMENT 'Полные геоданные в формате JSON',
    geo_data_center_json JSON COMMENT 'Геоданные центра в формате JSON',
    cluster_id INT NULL COMMENT 'ID кластера от k-means кластеризации',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Дата создания записи',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Дата последнего обновления',
    FOREIGN KEY (adm_area_id) REFERENCES adm_areas(id) ON DELETE SET NULL,
    FOREIGN KEY (district_id) REFERENCES districts(id) ON DELETE SET NULL,
    FOREIGN KEY (license_type_id) REFERENCES license_types(id) ON DELETE SET NULL,
    FOREIGN KEY (license_status_id) REFERENCES license_statuses(id) ON DELETE SET NULL,
    INDEX idx_global_id (global_id),
    INDEX idx_object_name (object_name(255)),
    INDEX idx_address (address(255)),
    INDEX idx_inn (inn),
    INDEX idx_kpp (kpp),
    INDEX idx_license_type (license_type_id),
    INDEX idx_license_status (license_status_id),
    INDEX idx_license_expire (license_expire),
    INDEX idx_adm_area (adm_area_id),
    INDEX idx_district (district_id),
    INDEX idx_coordinates (latitude, longitude),
    INDEX idx_cluster_id (cluster_id),
    INDEX idx_created_at (created_at),
    INDEX idx_updated_at (updated_at),
    INDEX idx_status_expire (license_status_id, license_expire),
    INDEX idx_type_status (license_type_id, license_status_id),
    INDEX idx_area_district (adm_area_id, district_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Основная таблица предприятий с алкогольными лицензиями';

-- ПРЕДСТАВЛЕНИЕ 
CREATE OR REPLACE VIEW companies_full AS
SELECT 
    c.id,
    c.global_id,
    c.object_name,
    c.address,
    aa.name AS adm_area,
    d.name AS district,
    c.subject_name,
    c.email,
    c.inn,
    c.kpp,
    lt.code AS license_type_code,
    lt.name AS license_type_name,
    c.license_number,
    c.license_number_in_registry,
    c.license_begin,
    c.license_expire,
    ls.status AS license_status,
    c.longitude,
    c.latitude,
    c.cluster_id,
    c.created_at,
    c.updated_at,
    DATEDIFF(c.license_expire, CURDATE()) AS days_until_expire,
    CASE 
        WHEN c.license_expire < CURDATE() THEN 'expired'
        WHEN DATEDIFF(c.license_expire, CURDATE()) <= 30 THEN 'expiring_soon'
        ELSE 'active'
    END AS license_status_color
FROM companies c
LEFT JOIN adm_areas aa ON c.adm_area_id = aa.id
LEFT JOIN districts d ON c.district_id = d.id
LEFT JOIN license_types lt ON c.license_type_id = lt.id
LEFT JOIN license_statuses ls ON c.license_status_id = ls.id;


CREATE TABLE IF NOT EXISTS user_favorites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    company_id INT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Внешние ключи для целостности данных
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE,
    
    -- Уникальность
    UNIQUE KEY unique_user_company (user_id, company_id),
    
    -- Индексы
    INDEX idx_user_id (user_id),
    INDEX idx_company_id (company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    privacy_policy_accepted BOOLEAN DEFAULT FALSE,
    data_processing_consent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    INDEX idx_email (email),
    INDEX idx_created_at (created_at),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Таблица пользователей системы';

-- Таблица сессий
CREATE TABLE IF NOT EXISTS user_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    session_token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45),
    user_agent TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_session_token (session_token),
    INDEX idx_user_id (user_id),
    INDEX idx_expires_at (expires_at),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Таблица сессий пользователей';

-- Таблица логов попыток входа
CREATE TABLE IF NOT EXISTS auth_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    action ENUM('login_attempt', 'login_success', 'login_failed', 'register_attempt', 'register_success', 'register_failed', 'logout', 'password_reset') NOT NULL,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at),
    INDEX idx_ip_address (ip_address)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Логи аутентификации';

-- Таблица для сброса пароля
CREATE TABLE IF NOT EXISTS password_resets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_token (token),
    INDEX idx_user_id (user_id),
    INDEX idx_expires_at (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Токены сброса пароля';
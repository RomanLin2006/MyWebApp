-- Простая таблица для избранных предприятий
CREATE TABLE IF NOT EXISTS user_favorites (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    company_id INT NOT NULL,
    company_name VARCHAR(500) NOT NULL,
    company_address VARCHAR(500),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Уникальность - пользователь не может добавить одно предприятие дважды
    UNIQUE KEY unique_user_company (user_id, company_id),
    
    -- Индексы для быстрого поиска
    INDEX idx_user_id (user_id),
    INDEX idx_company_id (company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Избранные предприятия пользователей';

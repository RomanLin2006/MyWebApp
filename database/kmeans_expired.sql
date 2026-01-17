DELIMITER //
CREATE PROCEDURE kmeans_expired_clustering(IN k INT) 
BEGIN 
    DECLARE iteration INT DEFAULT 0; 
    DECLARE converged BOOLEAN DEFAULT FALSE; 
    DECLARE centroid_changed INT DEFAULT 0; 
    DECLARE companies_count INT DEFAULT 0;
    
    -- Проверяем, достаточно ли просроченных компаний с координатами
    SELECT COUNT(*) INTO companies_count 
    FROM companies 
    WHERE latitude IS NOT NULL 
      AND longitude IS NOT NULL 
      AND license_status_id IN (3, 4, 5); -- Просроченные лицензии
    
    IF companies_count < k THEN
        SELECT CONCAT('Ошибка: доступно только ', companies_count, ' просроченных компаний с координатами, а нужно минимум ', k) as error;
    ELSE
        -- Создаем временные таблицы
        CREATE TEMPORARY TABLE temp_centroids ( 
            cluster_id INT PRIMARY KEY, 
            lat DECIMAL(10,8) NOT NULL, 
            lon DECIMAL(10,8) NOT NULL, 
            prev_lat DECIMAL(10,8) DEFAULT NULL, 
            prev_lon DECIMAL(10,8) DEFAULT NULL 
        ); 
         
        CREATE TEMPORARY TABLE temp_assignments ( 
            company_id INT PRIMARY KEY, 
            cluster_id INT NOT NULL, 
            distance DECIMAL(12,8) NOT NULL 
        ); 
         
        -- Инициализация центроидов случайными просроченными компаниями
        SET @cluster_num = 0; 
        INSERT INTO temp_centroids (cluster_id, lat, lon) 
        SELECT  
            (@cluster_num := @cluster_num + 1) as cluster_id, 
            latitude, 
            longitude 
        FROM ( 
            SELECT latitude, longitude 
            FROM companies 
            WHERE latitude IS NOT NULL 
              AND longitude IS NOT NULL 
              AND license_status_id IN (3, 4, 5) -- Просроченные лицензии
            ORDER BY RAND() 
            LIMIT k 
        ) as random_companies; 
         
        -- Основной цикл k-means
        main_loop: WHILE NOT converged DO 
            SET iteration = iteration + 1;
            
            -- Защита от бесконечного цикла (максимум 100 итераций)
            IF iteration > 100 THEN
                SELECT CONCAT('Достигнут лимит итераций: ', iteration) as warning;
                LEAVE main_loop;
            END IF;
             
            TRUNCATE TABLE temp_assignments; 
             
            -- Назначение каждой просроченной компании ближайшему центроиду
            INSERT INTO temp_assignments (company_id, cluster_id, distance) 
            SELECT  
              c.id, 
              ( 
              SELECT cent.cluster_id 
              FROM temp_centroids cent 
              ORDER BY SQRT(POW(c.latitude - cent.lat, 2) + POW(c.longitude - cent.lon, 2)) 
                  LIMIT 1 
              ) as cluster_id, 
              ( 
              SELECT MIN(SQRT(POW(c.latitude - cent.lat, 2) + POW(c.longitude - cent.lon, 2))) 
                  FROM temp_centroids cent 
              ) as distance 
            FROM companies c 
            WHERE c.latitude IS NOT NULL 
              AND c.longitude IS NOT NULL 
              AND c.license_status_id IN (3, 4, 5); -- Просроченные лицензии
         
            -- Сохранение предыдущих позиций центроидов
            UPDATE temp_centroids  
            SET prev_lat = lat, prev_lon = lon; 
             
            -- Пересчет центроидов как среднее координат просроченных компаний в кластере
            UPDATE temp_centroids cent 
            JOIN ( 
                SELECT  
                    a.cluster_id, 
                    AVG(c.latitude) as new_lat, 
                    AVG(c.longitude) as new_lon, 
                    COUNT(*) as companies_count 
                FROM temp_assignments a 
                JOIN companies c ON a.company_id = c.id 
                WHERE c.license_status_id IN (3, 4, 5) -- Просроченные лицензии
                GROUP BY a.cluster_id 
            ) new_cent ON cent.cluster_id = new_cent.cluster_id 
            SET cent.lat = new_cent.new_lat, 
                cent.lon = new_cent.new_lon; 

            -- Обработка пустых кластеров (переназначение случайными просроченными компаниями)
            UPDATE temp_centroids cent 
            LEFT JOIN ( 
                SELECT cluster_id, COUNT(*) as cnt 
                FROM temp_assignments 
                GROUP BY cluster_id 
            ) counts ON cent.cluster_id = counts.cluster_id 
            SET cent.lat = ( 
                    SELECT latitude FROM companies  
                    WHERE latitude IS NOT NULL 
                      AND longitude IS NOT NULL 
                      AND license_status_id IN (3, 4, 5) -- Просроченные лицензии
                    ORDER BY RAND() LIMIT 1 
                ), 
                cent.lon = ( 
                    SELECT longitude FROM companies  
                    WHERE latitude IS NOT NULL 
                      AND longitude IS NOT NULL 
                      AND license_status_id IN (3, 4, 5) -- Просроченные лицензии
                    ORDER BY RAND() LIMIT 1 
                ) 
            WHERE counts.cnt IS NULL OR counts.cnt = 0; 
         
            -- Проверка сходимости (изменились ли центроиды)
            SELECT COUNT(*) INTO centroid_changed 
            FROM temp_centroids 
            WHERE prev_lat IS NOT NULL  
              AND prev_lon IS NOT NULL 
              AND (ABS(lat - prev_lat) > 0.00001 OR ABS(lon - prev_lon) > 0.00001); 
             
            IF centroid_changed = 0 THEN 
                SET converged = TRUE; 
            END IF; 
             
        END WHILE; 
         
        -- Очистка предыдущих кластеров для просроченных
        UPDATE companies SET cluster_id = NULL WHERE license_status_id IN (3, 4, 5);

        -- Применение новых кластеров только для просроченных
        UPDATE companies c 
        JOIN temp_assignments a ON c.id = a.company_id 
        SET c.cluster_id = a.cluster_id 
        WHERE c.license_status_id IN (3, 4, 5);
         
        -- Возврат статистики по кластерам просроченных лицензий
        SELECT  
            c.cluster_id, 
            COUNT(*) as companies_count, 
            ROUND(AVG(c.latitude), 6) as avg_latitude, 
            ROUND(AVG(c.longitude), 6) as avg_longitude, 
            ROUND(MIN(c.latitude), 6) as min_latitude,
            ROUND(MAX(c.latitude), 6) as max_latitude,
            ROUND(MIN(c.longitude), 6) as min_longitude,
            ROUND(MAX(c.longitude), 6) as max_longitude,
            CONCAT('Итераций выполнено: ', iteration, ' (только просроченные)') as info 
        FROM companies c 
        WHERE c.cluster_id IS NOT NULL 
          AND c.license_status_id IN (3, 4, 5) -- Просроченные лицензии
        GROUP BY c.cluster_id 
        ORDER BY c.cluster_id; 
         
        -- Очистка временных таблиц
        DROP TEMPORARY TABLE temp_assignments;
        DROP TEMPORARY TABLE temp_centroids;
    END IF;
END // 
DELIMITER ;
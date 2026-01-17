import secrets
import hashlib
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import argon2
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import mysql.connector
from mysql.connector import Error
import logging

# Настройка Argon2
ph = PasswordHasher(
    time_cost=3,       # Количество итераций
    memory_cost=65536, # 64MB
    parallelism=4,     # 4 потока
    hash_len=32,       # 32 байта хэша
    salt_len=16        # 16 байт соли
)

class AuthManager:
    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        self.logger = logging.getLogger(__name__)
    
    def get_db_connection(self):
        """Безопасное подключение к базе данных"""
        try:
            connection = mysql.connector.connect(**self.db_config)
            return connection
        except Error as e:
            self.logger.error(f"Ошибка подключения к БД: {e}")
            raise
    
    def validate_email(self, email: str) -> bool:
        """Валидация email"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def validate_password(self, password: str) -> tuple[bool, str]:
        """Валидация пароля"""
        if len(password) < 8:
            return False, "Пароль должен содержать минимум 8 символов"
        
        if not re.search(r'[A-Z]', password):
            return False, "Пароль должен содержать хотя бы одну заглавную букву"
        
        if not re.search(r'[a-z]', password):
            return False, "Пароль должен содержать хотя бы одну строчную букву"
        
        if not re.search(r'\d', password):
            return False, "Пароль должен содержать хотя бы одну цифру"
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Пароль должен содержать хотя бы один специальный символ"
        
        return True, "Пароль соответствует требованиям"
    
    def hash_password(self, password: str) -> str:
        """Хэширование пароля с помощью Argon2"""
        return ph.hash(password)
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Проверка пароля"""
        try:
            return ph.verify(hashed, password)
        except VerifyMismatchError:
            return False
        except Exception as e:
            self.logger.error(f"Ошибка проверки пароля: {e}")
            return False
    
    def generate_session_token(self) -> str:
        """Генерация безопасного токена сессии"""
        return secrets.token_urlsafe(32)
    
    def log_auth_action(self, email: str, action: str, ip_address: str = None, 
                       user_agent: str = None, details: str = None):
        """Логирование действий аутентификации"""
        try:
            connection = self.get_db_connection()
            cursor = connection.cursor()
            
            query = """
            INSERT INTO auth_logs (email, ip_address, user_agent, action, details)
            VALUES (%s, %s, %s, %s, %s)
            """
            
            cursor.execute(query, (email, ip_address, user_agent, action, details))
            connection.commit()
            
        except Error as e:
            self.logger.error(f"Ошибка логирования: {e}")
        finally:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()
    
    def register_user(self, email: str, password: str, first_name: str = None, 
                     last_name: str = None, phone: str = None, 
                     privacy_policy_accepted: bool = False,
                     data_processing_consent: bool = False,
                     ip_address: str = None, user_agent: str = None) -> Dict[str, Any]:
        """Регистрация пользователя с защитой от SQL-инъекций"""
        
        # Валидация данных
        if not self.validate_email(email):
            return {"success": False, "message": "Некорректный email адрес"}
        
        password_valid, password_message = self.validate_password(password)
        if not password_valid:
            return {"success": False, "message": password_message}
        
        if not privacy_policy_accepted:
            return {"success": False, "message": "Необходимо принять политику конфиденциальности"}
        
        if not data_processing_consent:
            return {"success": False, "message": "Необходимо дать согласие на обработку персональных данных"}
        
        try:
            connection = self.get_db_connection()
            cursor = connection.cursor()
            
            # Проверка существования пользователя
            check_query = "SELECT id FROM users WHERE email = %s"
            cursor.execute(check_query, (email,))
            
            if cursor.fetchone():
                self.log_auth_action(email, "register_failed", ip_address, user_agent, "Email уже существует")
                return {"success": False, "message": "Пользователь с таким email уже существует"}
            
            # Хэширование пароля
            password_hash = self.hash_password(password)
            
            # Создание пользователя с параметризованным запросом
            insert_query = """
            INSERT INTO users (email, password_hash, first_name, last_name, phone, 
                             privacy_policy_accepted, data_processing_consent)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(insert_query, (
                email.lower(), password_hash, first_name, last_name, phone,
                privacy_policy_accepted, data_processing_consent
            ))
            
            user_id = cursor.lastrowid
            connection.commit()
            
            self.log_auth_action(email, "register_success", ip_address, user_agent, f"User ID: {user_id}")
            
            return {
                "success": True, 
                "message": "Регистрация успешна",
                "user_id": user_id
            }
            
        except Error as e:
            self.logger.error(f"Ошибка регистрации: {e}")
            self.log_auth_action(email, "register_failed", ip_address, user_agent, f"DB Error: {str(e)}")
            return {"success": False, "message": "Ошибка при регистрации"}
        finally:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()
    
    def login_user(self, email: str, password: str, ip_address: str = None, 
                  user_agent: str = None) -> Dict[str, Any]:
        """Вход пользователя с защитой от SQL-инъекций"""
        
        if not self.validate_email(email):
            return {"success": False, "message": "Некорректный email адрес"}
        
        try:
            connection = self.get_db_connection()
            cursor = connection.cursor(dictionary=True)
            
            self.log_auth_action(email, "login_attempt", ip_address, user_agent)
            
            # Поиск пользователя с параметризованным запросом
            query = """
            SELECT id, email, password_hash, first_name, last_name, is_active, 
                   email_verified, last_login
            FROM users 
            WHERE email = %s AND is_active = TRUE
            """
            
            cursor.execute(query, (email.lower(),))
            user = cursor.fetchone()
            
            if not user:
                self.log_auth_action(email, "login_failed", ip_address, user_agent, "User not found")
                return {"success": False, "message": "Неверный email или пароль"}
            
            # Проверка пароля
            if not self.verify_password(password, user['password_hash']):
                self.log_auth_action(email, "login_failed", ip_address, user_agent, "Invalid password")
                return {"success": False, "message": "Неверный email или пароль"}
            
            # Создание сессии
            session_token = self.generate_session_token()
            expires_at = datetime.now() + timedelta(days=7)  # Сессия на 7 дней
            
            # Вставка сессии с параметризованным запросом
            session_query = """
            INSERT INTO user_sessions (user_id, session_token, expires_at, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s)
            """
            
            cursor.execute(session_query, (
                user['id'], session_token, expires_at, ip_address, user_agent
            ))
            
            # Обновление времени последнего входа
            update_query = "UPDATE users SET last_login = NOW() WHERE id = %s"
            cursor.execute(update_query, (user['id'],))
            
            connection.commit()
            
            self.log_auth_action(email, "login_success", ip_address, user_agent, f"Session: {session_token[:10]}...")
            
            return {
                "success": True,
                "message": "Вход выполнен успешно",
                "session_token": session_token,
                "user": {
                    "id": user['id'],
                    "email": user['email'],
                    "first_name": user['first_name'],
                    "last_name": user['last_name'],
                    "email_verified": user['email_verified']
                }
            }
            
        except Error as e:
            self.logger.error(f"Ошибка входа: {e}")
            self.log_auth_action(email, "login_failed", ip_address, user_agent, f"DB Error: {str(e)}")
            return {"success": False, "message": "Ошибка при входе"}
        finally:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()
    
    def validate_session(self, session_token: str) -> Dict[str, Any]:
        """Валидация сессии"""
        try:
            connection = self.get_db_connection()
            cursor = connection.cursor(dictionary=True)
            
            # Поиск сессии с параметризованным запросом
            query = """
            SELECT s.user_id, s.expires_at, u.email, u.first_name, u.last_name, u.is_active
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_token = %s AND s.is_active = TRUE AND u.is_active = TRUE
            """
            
            cursor.execute(query, (session_token,))
            session = cursor.fetchone()
            
            if not session:
                return {"valid": False, "message": "Сессия не найдена"}
            
            # Проверка срока действия
            if datetime.now() > session['expires_at']:
                # Деактивация просроченной сессии
                update_query = "UPDATE user_sessions SET is_active = FALSE WHERE session_token = %s"
                cursor.execute(update_query, (session_token,))
                connection.commit()
                return {"valid": False, "message": "Сессия истекла"}
            
            return {
                "valid": True,
                "user": {
                    "id": session['user_id'],
                    "email": session['email'],
                    "first_name": session['first_name'],
                    "last_name": session['last_name']
                }
            }
            
        except Error as e:
            self.logger.error(f"Ошибка валидации сессии: {e}")
            return {"valid": False, "message": "Ошибка проверки сессии"}
        finally:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()
    
    def logout_user(self, session_token: str, ip_address: str = None) -> Dict[str, Any]:
        """Выход пользователя"""
        try:
            connection = self.get_db_connection()
            cursor = connection.cursor()
            
            # Деактивация сессии
            query = "UPDATE user_sessions SET is_active = FALSE WHERE session_token = %s"
            cursor.execute(query, (session_token,))
            
            affected_rows = cursor.rowcount
            connection.commit()
            
            if affected_rows > 0:
                return {"success": True, "message": "Выход выполнен успешно"}
            else:
                return {"success": False, "message": "Сессия не найдена"}
            
        except Error as e:
            self.logger.error(f"Ошибка выхода: {e}")
            return {"success": False, "message": "Ошибка при выходе"}
        finally:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()
// Модуль аутентификации
class AuthManager {
    constructor() {
        this.sessionToken = localStorage.getItem('sessionToken');
        this.currentUser = null;
        this.apiBaseUrl = 'http://localhost:5000/api/auth';
        
        this.init();
    }

    init() {
        // Проверяем сессию при загрузке страницы
        if (this.sessionToken) {
            this.validateSession();
        }

        // Назначаем обработчики событий
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Кнопки в шапке
        document.getElementById('loginBtn')?.addEventListener('click', () => this.showLoginModal());
        document.getElementById('registerBtn')?.addEventListener('click', () => this.showRegisterModal());
        document.getElementById('logoutBtn')?.addEventListener('click', () => this.logout());

        // Формы
        document.getElementById('loginForm')?.addEventListener('submit', (e) => this.handleLogin(e));
        document.getElementById('registerForm')?.addEventListener('submit', (e) => this.handleRegister(e));

        // Переключение между модальными окнами
        document.getElementById('showRegisterFromLogin')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.hideLoginModal();
            this.showRegisterModal();
        });

        document.getElementById('showLoginFromRegister')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.hideRegisterModal();
            this.showLoginModal();
        });

        // Валидация паролей при регистрации
        document.getElementById('registerPassword')?.addEventListener('input', (e) => {
            this.validatePasswordStrength(e.target.value);
        });

        document.getElementById('registerPasswordConfirm')?.addEventListener('input', (e) => {
            this.validatePasswordMatch();
        });
    }

    showLoginModal() {
        const modal = new bootstrap.Modal(document.getElementById('loginModal'));
        modal.show();
    }

    hideLoginModal() {
        const modal = bootstrap.Modal.getInstance(document.getElementById('loginModal'));
        modal?.hide();
    }

    showRegisterModal() {
        const modal = new bootstrap.Modal(document.getElementById('registerModal'));
        modal.show();
    }

    hideRegisterModal() {
        const modal = bootstrap.Modal.getInstance(document.getElementById('registerModal'));
        modal?.hide();
    }

    async handleLogin(event) {
        event.preventDefault();
        
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;

        if (!email || !password) {
            this.showNotification('Пожалуйста, заполните все поля', 'error');
            return;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ email, password })
            });

            const data = await response.json();

            if (data.success) {
                this.sessionToken = data.session_token;
                this.currentUser = data.user;
                
                localStorage.setItem('sessionToken', this.sessionToken);
                localStorage.setItem('currentUser', JSON.stringify(this.currentUser));
                
                this.updateUI();
                this.hideLoginModal();
                this.showNotification('Вход выполнен успешно!', 'success');
                
                // Очищаем форму
                document.getElementById('loginForm').reset();
            } else {
                this.showNotification(data.message || 'Ошибка входа', 'error');
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showNotification('Ошибка соединения с сервером', 'error');
        }
    }

    async handleRegister(event) {
        event.preventDefault();
        
        const formData = {
            email: document.getElementById('registerEmail').value,
            password: document.getElementById('registerPassword').value,
            password_confirm: document.getElementById('registerPasswordConfirm').value,
            first_name: document.getElementById('registerFirstName').value,
            last_name: document.getElementById('registerLastName').value,
            phone: document.getElementById('registerPhone').value,
            privacy_policy_accepted: document.getElementById('privacyPolicy').checked,
            data_processing_consent: document.getElementById('dataProcessingConsent').checked
        };

        // Валидация
        if (!this.validateRegisterForm(formData)) {
            return;
        }

        try {
            const response = await fetch(`${this.apiBaseUrl}/register`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            });

            const data = await response.json();

            if (data.success) {
                this.hideRegisterModal();
                this.showNotification('Регистрация успешна! Теперь вы можете войти.', 'success');
                
                // Очищаем форму
                document.getElementById('registerForm').reset();
                
                // Показываем модальное окно входа
                setTimeout(() => this.showLoginModal(), 1500);
            } else {
                this.showNotification(data.message || 'Ошибка регистрации', 'error');
            }
        } catch (error) {
            console.error('Register error:', error);
            this.showNotification('Ошибка соединения с сервером', 'error');
        }
    }

    validateRegisterForm(formData) {
        if (!formData.email || !formData.password) {
            this.showNotification('Пожалуйста, заполните обязательные поля', 'error');
            return false;
        }

        if (formData.password !== formData.password_confirm) {
            this.showNotification('Пароли не совпадают', 'error');
            return false;
        }

        if (!formData.privacy_policy_accepted) {
            this.showNotification('Необходимо принять политику конфиденциальности', 'error');
            return false;
        }

        if (!formData.data_processing_consent) {
            this.showNotification('Необходимо дать согласие на обработку персональных данных', 'error');
            return false;
        }

        const passwordValidation = this.validatePasswordStrength(formData.password);
        if (!passwordValidation.valid) {
            this.showNotification(passwordValidation.message, 'error');
            return false;
        }

        return true;
    }

    validatePasswordStrength(password) {
        if (password.length < 8) {
            return { valid: false, message: 'Пароль должен содержать минимум 8 символов' };
        }

        if (!/[A-Z]/.test(password)) {
            return { valid: false, message: 'Пароль должен содержать хотя бы одну заглавную букву' };
        }

        if (!/[a-z]/.test(password)) {
            return { valid: false, message: 'Пароль должен содержать хотя бы одну строчную букву' };
        }

        if (!/\d/.test(password)) {
            return { valid: false, message: 'Пароль должен содержать хотя бы одну цифру' };
        }

        if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
            return { valid: false, message: 'Пароль должен содержать хотя бы один специальный символ' };
        }

        return { valid: true, message: 'Пароль соответствует требованиям' };
    }

    validatePasswordMatch() {
        const password = document.getElementById('registerPassword').value;
        const confirmPassword = document.getElementById('registerPasswordConfirm').value;
        const confirmField = document.getElementById('registerPasswordConfirm');
        
        if (confirmPassword && password !== confirmPassword) {
            confirmField.setCustomValidity('Пароли не совпадают');
        } else {
            confirmField.setCustomValidity('');
        }
    }

    async validateSession() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/validate`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ session_token: this.sessionToken })
            });

            const data = await response.json();

            if (data.valid) {
                this.currentUser = data.user;
                this.updateUI();
            } else {
                this.clearSession();
            }
        } catch (error) {
            console.error('Session validation error:', error);
            this.clearSession();
        }
    }

    async logout() {
        if (!this.sessionToken) return;

        try {
            await fetch(`${this.apiBaseUrl}/logout`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ session_token: this.sessionToken })
            });
        } catch (error) {
            console.error('Logout error:', error);
        }

        this.clearSession();
        this.showNotification('Выход выполнен успешно', 'success');
    }

    clearSession() {
        this.sessionToken = null;
        this.currentUser = null;
        localStorage.removeItem('sessionToken');
        localStorage.removeItem('currentUser');
        this.updateUI();
    }

    updateUI() {
        const authButtons = document.getElementById('authButtons');
        const userInfo = document.getElementById('userInfo');
        const userName = document.getElementById('userName');

        if (this.currentUser) {
            // Пользователь авторизован
            authButtons.style.display = 'none';
            userInfo.style.display = 'flex';
            
            const displayName = this.currentUser.first_name || this.currentUser.email;
            userName.textContent = displayName;
        } else {
            // Пользователь не авторизован
            authButtons.style.display = 'flex';
            userInfo.style.display = 'none';
        }
    }

    showNotification(message, type = 'info') {
        // Создаем уведомление
        const notification = document.createElement('div');
        notification.className = `alert alert-${type === 'error' ? 'danger' : type} position-fixed`;
        notification.style.cssText = `
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 300px;
            animation: slideInRight 0.3s ease;
        `;
        
        notification.innerHTML = `
            <div class="d-flex justify-content-between align-items-center">
                <span>${message}</span>
                <button type="button" class="btn-close ms-2" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;

        document.body.appendChild(notification);

        // Автоматически удаляем через 5 секунд
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }

    // Получение заголовка авторизации для API запросов
    getAuthHeaders() {
        return this.sessionToken ? {
            'Authorization': `Bearer ${this.sessionToken}`,
            'Content-Type': 'application/json'
        } : {
            'Content-Type': 'application/json'
        };
    }

    // Проверка авторизации
    isAuthenticated() {
        return !!this.currentUser && !!this.sessionToken;
    }
}

// Инициализация модуля аутентификации
let authManager;
document.addEventListener('DOMContentLoaded', () => {
    authManager = new AuthManager();
});

// Экспорт для использования в других модулях
window.authManager = authManager;

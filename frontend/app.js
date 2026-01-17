// ============================================
// ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
// ============================================
const API_BASE = "http://127.0.0.1:5000";
let map = null;
let markersLayer = null;
let allCompaniesData = [];

// Глобальные переменные для хранения состояния
let originalMarkersData = [];
let isSimilarMode = false;

// ============================================
// ИНИЦИАЛИЗАЦИЯ КАРТЫ
// ============================================
function initMap() {
  map = L.map("map").setView([55.75, 37.62], 10);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 18,
  }).addTo(map);

  markersLayer = L.layerGroup().addTo(map);
  
  // Добавляем индикатор масштаба
  L.control.scale({
    position: 'bottomleft',
    metric: true,
    imperial: false,
    updateWhenIdle: true
  }).addTo(map);
  
  // Добавляем индикатор масштаба в левый верхний угол
  const scaleIndicator = document.createElement('div');
  scaleIndicator.style.cssText = `
    position: fixed;
    top: 20px;
    left: 20px;
    background: rgba(255, 255, 255, 0.9);
    border: 1px solid #ccc;
    border-radius: 4px;
    padding: 8px 12px;
    z-index: 1000;
    font-size: 12px;
    font-weight: 500;
  `;
  scaleIndicator.id = 'scaleIndicator';
  document.body.appendChild(scaleIndicator);
  
  // Обновляем индикатор при изменении масштаба
  map.on('zoomend', function() {
    const zoom = map.getZoom();
    let meters = '';
    
    if (zoom <= 8) meters = '~1000 м';
    else if (zoom <= 10) meters = '~500 м';
    else if (zoom <= 12) meters = '~200 м';
    else if (zoom <= 14) meters = '~100 м';
    else if (zoom <= 16) meters = '~50 м';
    else meters = '~10 м';
    
    scaleIndicator.innerHTML = `Масштаб: ${zoom} | ${meters}`;
    
    // Обновляем данные только если не в режиме похожих
    if (!isSimilarMode) {
      loadCompanies();
    }
  });
  
  // Добавляем обработчики для динамической загрузки
  map.on('moveend', function() {
    // Обновляем данные только если не в режиме похожих
    if (!isSimilarMode) {
      clearTimeout(window.mapMoveTimeout);
      window.mapMoveTimeout = setTimeout(() => {
        loadCompanies();
      }, 500); // 500ms debounce
    }
  });
  
  // Инициализация
  scaleIndicator.innerHTML = 'Масштаб: 10 | ~500 м';
}


// ============================================
// УПРАВЛЕНИЕ ПАНЕЛЬЮ ФИЛЬТРОВ
// ============================================
function initFiltersPanel() {
  const container = document.querySelector('.filters-panel-container');
  const trigger = document.getElementById('filtersTrigger');
  const panel = document.getElementById('filtersPanel');
  
  // Наведение на контейнер - открывает панель
  container.addEventListener('mouseenter', () => {
    container.classList.add('open');
  });
  
  // Уход с контейнера - закрывает панель
  container.addEventListener('mouseleave', () => {
    container.classList.remove('open');
  });
  
  // Клик на триггер - переключает панель
  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    container.classList.toggle('open');
  });
  
  // Клик вне панели - закрывает её
  document.addEventListener('click', (e) => {
    if (!container.contains(e.target)) {
      container.classList.remove('open');
    }
  });
}

// ============================================
// ЗАГРУЗКА ОПЦИЙ ФИЛЬТРОВ
// ============================================
async function loadFilterOptions() {
  try {
    const response = await fetch(`${API_BASE}/api/filters/options`);
    const data = await response.json();

    // Заполняем округа
    const admAreaSelect = document.getElementById("admAreaFilter");
    data.adm_areas.forEach(area => {
      const option = document.createElement("option");
      option.value = area;
      option.textContent = area;
      admAreaSelect.appendChild(option);
    });

    // Заполняем районы
    const districtSelect = document.getElementById("districtFilter");
    data.districts.forEach(district => {
      const option = document.createElement("option");
      option.value = district;
      option.textContent = district;
      districtSelect.appendChild(option);
    });

    // Заполняем типы лицензий
    const licenseTypeSelect = document.getElementById("licenseTypeFilter");
    data.license_types.forEach(type => {
      const option = document.createElement("option");
      option.value = type.code;
      option.textContent = `${type.code} - ${type.name}`;
      licenseTypeSelect.appendChild(option);
    });

  } catch (error) {
    console.error("Ошибка загрузки опций фильтров:", error);
  }
}

// ============================================
// ЗАГРУЗКА КОМПАНИЙ
// ============================================
async function loadCompanies() {
  // Не загружаем данные если в режиме похожих
  if (isSimilarMode) {
    return;
  }
  
  const params = new URLSearchParams();
  
  // Определяем текущий масштаб и границы
  const zoom = map.getZoom();
  const bounds = map.getBounds();
  
  // Логика загрузки в зависимости от масштаба
  if (zoom >= 16) {
    // Детальный масштаб (16+) - загружаем все в видимой области
    params.set("load_all", "true");
    params.set("bounds", `${bounds.getSouth()},${bounds.getWest()},${bounds.getNorth()},${bounds.getEast()}`);
    params.set("zoom_level", zoom);
  } else if (zoom >= 12) {
    // Средний масштаб (12-15) - ограничение 1000 точек
    params.set("limit", "1000");
  } else {
    // Общий масштаб (11 и меньше) - ограничение 500 точек
    params.set("limit", "500");
  }

  // Собираем фильтры (работают при любом масштабе)
  const statusColor = document.getElementById("statusFilter").value;
  if (statusColor) params.set("status_color", statusColor);

  const admArea = document.getElementById("admAreaFilter").value;
  if (admArea) params.set("adm_area", admArea);

  const district = document.getElementById("districtFilter").value;
  if (district) params.set("district", district);

  const licenseType = document.getElementById("licenseTypeFilter").value;
  if (licenseType) params.set("license_type", licenseType);

  const search = document.getElementById("searchInput").value.trim();
  if (search) params.set("search", search);

  try {
    const resp = await fetch(`${API_BASE}/api/companies?${params.toString()}`);
    
    if (!resp.ok) {
      throw new Error(`HTTP error! status: ${resp.status}`);
    }
    
    const data = await resp.json();
    
    if (!Array.isArray(data)) {
      console.error('Invalid data format:', data);
      alert('Ошибка: получены данные в неверном формате');
      return;
    }

    // Сохраняем все загруженные данные
    allCompaniesData = data;

    markersLayer.clearLayers();

    let count = 0;
    data.forEach((c) => {
      if (c.latitude == null || c.longitude == null) return;

      const color = getColorByStatusColor(c.license_status_color);
      const markerClass = getMarkerClass(c.license_status_color);

      const marker = L.circleMarker([c.latitude, c.longitude], {
        radius: 8,
        color: color,
        fillColor: color,
        fillOpacity: 0.85,
        weight: 2.5,
        className: markerClass,
      });

      const popupHtml = `
        <div class="popup-content">
          <strong>${c.object_name || "Без названия"}</strong>
          <hr/>
          <div class="popup-details">
            <div><strong>Адрес:</strong> ${c.address || "-"}</div>
            <div><strong>Округ:</strong> ${c.adm_area || "-"}</div>
            <div><strong>Район:</strong> ${c.district || "-"}</div>
            <div><strong>Тип работ:</strong> ${c.license_type_name || "-"} (${c.license_type_code || "-"})</div>
            <div><strong>Лицензия:</strong> ${c.license_number || "-"}</div>
            <div><strong>Действует:</strong> ${c.license_begin || "-"} - ${c.license_expire || "-"}</div>
            <div><strong>Статус:</strong> ${c.license_status || "-"}</div>
            ${c.inn ? `<div><strong>ИНН:</strong> ${c.inn}</div>` : ""}
          </div>
          <hr/>
          <div class="popup-actions">
            <button class="btn-sm btn-warning" id="favoriteBtn-${c.id}" onclick="toggleFavorite(${c.id})">
              <i class="bi bi-star" id="favoriteIcon-${c.id}"></i> 
              <span id="favoriteText-${c.id}">Добавить в избранное</span>
            </button>
            <button class="btn-sm btn-primary" onclick="findSimilarCompanies(${c.latitude}, ${c.longitude}, '${c.license_type_code}', '${c.inn || ''}')">
              🔍 Поиск похожих (1000м)
            </button>
          </div>
        </div>
      `;
      
      marker.bindPopup(popupHtml, {
        className: "custom-popup",
        maxWidth: 420,
        autoClose: false,
        closeOnClick: false,
        closeOnEscapeKey: false
      });

      // Сохраняем данные компании в маркере
      marker._companyData = c;

      // Hover эффекты
      const originalRadius = 8;
      const hoveredRadius = 11;

      marker.on("mouseover", function (e) {
        marker.setRadius(hoveredRadius);
        marker.setStyle({
          fillColor: getHoverColor(c.license_status_color),
          color: getHoverStroke(c.license_status_color),
          weight: 3,
        });
        if (marker._path) {
          marker._path.classList.add("hovered");
        }
      });

      marker.on("mouseout", function (e) {
        marker.setRadius(originalRadius);
        marker.setStyle({
          fillColor: color,
          color: color,
          weight: 2.5,
        });
        if (marker._path) {
          marker._path.classList.remove("hovered");
        }
      });

      marker.on("click", function (e) {
        marker.openPopup();
      });
      marker.addTo(markersLayer);
      count++;
    });

    // Обновляем счётчик точек с информацией о режиме загрузки
    let countText = `${count} точек`;
    if (zoom >= 16) {
      countText += " (все в области)";
    } else if (zoom >= 12) {
      countText += " (лимит 1000)";
    } else {
      countText += " (лимит 500)";
    }
    document.getElementById("pointsCount").textContent = countText;
    
    // Обновляем состояние кнопок избранного для загруженных компаний
    updateFavoriteButtonsState();
    
  } catch (e) {
    console.error(e);
    alert("Ошибка при загрузке данных с backend. Проверь, что Flask запущен.");
  }
}

// ============================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ============================================
function showNotification(message, type = 'success') {
  // Создаем уведомление
  const notification = document.createElement('div');
  const colors = {
    success: '#4CAF50',
    error: '#f44336',
    warning: '#ff9800',
    info: '#2196F3'
  };
  
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: ${colors[type] || colors.success};
    color: white;
    padding: 12px 20px;
    border-radius: 4px;
    z-index: 10000;
    font-size: 14px;
    font-weight: 500;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    animation: slideIn 0.3s ease-out;
  `;
  notification.textContent = message;
  
  document.body.appendChild(notification);
  
  // Автоматически удаляем через 3 секунды
  setTimeout(() => {
    notification.style.animation = 'slideOut 0.3s ease-out';
    setTimeout(() => {
      if (notification.parentNode) {
        notification.parentNode.removeChild(notification);
      }
    }, 300);
  }, 3000);
}

function getColorByStatusColor(statusColor) {
  if (statusColor === "expired") return "#ef4444";
  if (statusColor === "expiring_soon") return "#f59e0b";
  return "#10b981";
}

function getMarkerClass(statusColor) {
  if (statusColor === "expired") return "marker-expired";
  if (statusColor === "expiring_soon") return "marker-expiring";
  return "marker-active";
}

function getHoverColor(statusColor) {
  if (statusColor === "expired") return "#f87171";
  if (statusColor === "expiring_soon") return "#fbbf24";
  return "#34d399";
}

function getHoverStroke(statusColor) {
  if (statusColor === "expired") return "#ef4444";
  if (statusColor === "expiring_soon") return "#f59e0b";
  return "#10b981";
}

// ============================================
// ФУНКЦИИ АНАЛИЗА
// ============================================
function findSimilarCompanies(lat, lon, licenseType, excludeInn) {
  // Сохраняем текущие маркеры если еще не в режиме похожих
  if (!isSimilarMode) {
    originalMarkersData = [];
    markersLayer.eachLayer(marker => {
      originalMarkersData.push(marker);
    });
    isSimilarMode = true;
  }
  
  // Находим похожие предприятия в радиусе 1000м
  const similar = allCompaniesData.filter(company => {
    if (company.latitude == null || company.longitude == null) return false;
    if (company.inn === excludeInn) return false; // Исключаем текущее предприятие
    if (company.license_type_code !== licenseType) return false; // Такой же тип лицензии
    
    // Расчет расстояния (упрощенный)
    const distance = Math.sqrt(
      Math.pow(company.latitude - lat, 2) + 
      Math.pow(company.longitude - lon, 2)
    ) * 111000; // Примерно 111км на 1 градус
    
    return distance <= 1000; // 1000 метров
  });

  // Очищаем карту и показываем только похожие предприятия
  markersLayer.clearLayers();
  
  similar.forEach((c) => {
    const color = getColorByStatusColor(c.license_status_color);
    const markerClass = getMarkerClass(c.license_status_color);

    const marker = L.circleMarker([c.latitude, c.longitude], {
      radius: 10, // Увеличенный размер для похожих
      color: color,
      fillColor: color,
      fillOpacity: 0.9,
      weight: 3,
      className: markerClass + ' similar-highlighted',
    });

    const popupHtml = `
      <div class="popup-content">
        <strong>${c.object_name || "Без названия"}</strong>
        <hr/>
        <div class="popup-details">
          <div><strong>Адрес:</strong> ${c.address || "-"}</div>
          <div><strong>Округ:</strong> ${c.adm_area || "-"}</div>
          <div><strong>Район:</strong> ${c.district || "-"}</div>
          <div><strong>Тип работ:</strong> ${c.license_type_name || "-"} (${c.license_type_code || "-"})</div>
          <div><strong>Лицензия:</strong> ${c.license_number || "-"}</div>
          <div><strong>Действует:</strong> ${c.license_begin || "-"} - ${c.license_expire || "-"}</div>
          <div><strong>Статус:</strong> ${c.license_status || "-"}</div>
          ${c.inn ? `<div><strong>ИНН:</strong> ${c.inn}</div>` : ""}
        </div>
      </div>
    `;
    
    marker.bindPopup(popupHtml, {
      className: "custom-popup",
      maxWidth: 420,
      autoClose: false,
      closeOnClick: false,
      closeOnEscapeKey: false
    });

    marker.addTo(markersLayer);
  });

  // Показываем уведомление
  showNotification(`Найдено ${similar.length} похожих предприятий в радиусе 1000м`);
  
  // Обновляем счетчик
  document.getElementById("pointsCount").textContent = `${similar.length} точек (похожие)`;
}

// ============================================
// ОЧИСТКА ФИЛЬТРОВ
// ============================================
function clearFilters() {
  document.getElementById("searchInput").value = "";
  document.getElementById("statusFilter").value = "";
  document.getElementById("admAreaFilter").value = "";
  document.getElementById("districtFilter").value = "";
  document.getElementById("licenseTypeFilter").value = "";
  
  // Возвращаем исходные маркеры если был режим похожих
  if (isSimilarMode) {
    markersLayer.clearLayers();
    originalMarkersData.forEach(marker => {
      markersLayer.addLayer(marker);
    });
    originalMarkersData = [];
    isSimilarMode = false;
  }
  
  loadCompanies();
}

// ============================================
// ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ
// ============================================
document.addEventListener("DOMContentLoaded", function () {
  initMap();
  initFiltersPanel();
  loadFilterOptions();
  loadCompanies();

  // Обработчики событий
  document.getElementById("loadBtn").addEventListener("click", loadCompanies);
  document.getElementById("clearFiltersBtn").addEventListener("click", clearFilters);
  
  // Фильтры применяются автоматически при изменении
  const filterElements = [
    "statusFilter", "admAreaFilter", "districtFilter", "licenseTypeFilter"
  ];
  
  filterElements.forEach(id => {
    document.getElementById(id).addEventListener("change", loadCompanies);
  });
  
  // Поиск с задержкой
  let searchTimeout;
  document.getElementById("searchInput").addEventListener("input", function(e) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      loadCompanies();
    }, 500);
  });
  
  // Обработчик для кнопки избранного
  const favoritesBtn = document.getElementById('favoritesBtn');
  if (favoritesBtn) {
    favoritesBtn.addEventListener('click', showFavorites);
  }
  
  // Обновляем счетчик избранных при загрузке
  updateFavoritesCount();
});

// ============================================
// ФУНКЦИИ РАБОТЫ С ИЗБРАННЫМИ
// ============================================
async function toggleFavorite(companyId) {
  const token = localStorage.getItem('sessionToken');
  if (!token) {
    showNotification('Для добавления в избранное необходимо войти в систему', 'warning');
    return;
  }

  try {
    // Проверяем текущее состояние
    const checkResponse = await fetch(`${API_BASE}/api/favorites/check/${companyId}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    const checkData = await checkResponse.json();
    
    if (checkData.is_favorite) {
      // Удаляем из избранного
      const deleteResponse = await fetch(`${API_BASE}/api/favorites/${companyId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (deleteResponse.ok) {
        updateFavoriteButton(companyId, false);
        showNotification('Предприятие удалено из избранного', 'success');
        updateFavoritesCount();
      } else {
        showNotification('Ошибка при удалении из избранного', 'error');
      }
    } else {
      // Добавляем в избранное
      const addResponse = await fetch(`${API_BASE}/api/favorites`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          company_id: companyId
        })
      });
      
      if (addResponse.ok) {
        updateFavoriteButton(companyId, true);
        showNotification('Предприятие добавлено в избранное', 'success');
        updateFavoritesCount();
      } else {
        const errorData = await addResponse.json();
        showNotification(errorData.error || 'Ошибка при добавлении в избранное', 'error');
      }
    }
  } catch (error) {
    console.error('Ошибка при работе с избранными:', error);
    showNotification('Ошибка при работе с избранными', 'error');
  }
}

function updateFavoriteButton(companyId, isFavorite) {
  const btn = document.getElementById(`favoriteBtn-${companyId}`);
  const icon = document.getElementById(`favoriteIcon-${companyId}`);
  const text = document.getElementById(`favoriteText-${companyId}`);
  
  if (!btn || !icon || !text) return;
  
  if (isFavorite) {
    btn.className = 'btn-sm btn-danger';
    icon.className = 'bi bi-star-fill';
    text.textContent = 'Удалить из избранного';
  } else {
    btn.className = 'btn-sm btn-warning';
    icon.className = 'bi bi-star';
    text.textContent = 'Добавить в избранное';
  }
}

async function updateFavoritesCount() {
  const token = localStorage.getItem('sessionToken');
  if (!token) {
    document.getElementById('favoritesCount').style.display = 'none';
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/favorites`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      const count = data.favorites ? data.favorites.length : 0;
      const countElement = document.getElementById('favoritesCount');
      
      if (count > 0) {
        countElement.textContent = count;
        countElement.style.display = 'inline-block';
      } else {
        countElement.style.display = 'none';
      }
    }
  } catch (error) {
    console.error('Ошибка при обновлении счетчика избранных:', error);
  }
}

async function updateFavoriteButtonsState() {
  const token = localStorage.getItem('sessionToken');
  if (!token) return;

  try {
    // Получаем список избранных
    const response = await fetch(`${API_BASE}/api/favorites`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (!response.ok) return;
    
    const data = await response.json();
    const favoriteIds = data.favorites ? data.favorites.map(f => f.company_id) : [];
    
    // Обновляем состояние кнопок для текущих компаний
    allCompaniesData.forEach(company => {
      const isFavorite = favoriteIds.includes(company.id);
      updateFavoriteButton(company.id, isFavorite);
    });
    
  } catch (error) {
    console.error('Ошибка при обновлении состояния кнопок избранного:', error);
  }
}

async function showFavorites() {
  const token = localStorage.getItem('sessionToken');
  if (!token) {
    showNotification('Для просмотра избранных необходимо войти в систему', 'warning');
    return;
  }

  const modal = new bootstrap.Modal(document.getElementById('favoritesModal'));
  const content = document.getElementById('favoritesContent');
  
  // Показываем загрузку
  content.innerHTML = `
    <div class="text-center">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Загрузка...</span>
      </div>
      <p class="mt-2">Загрузка избранных предприятий...</p>
    </div>
  `;
  
  modal.show();

  try {
    const response = await fetch(`${API_BASE}/api/favorites`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (!response.ok) {
      throw new Error('Ошибка загрузки избранных');
    }
    
    const data = await response.json();
    
    if (!data.favorites || data.favorites.length === 0) {
      content.innerHTML = `
        <div class="text-center py-5">
          <i class="bi bi-star" style="font-size: 3rem; color: #ccc;"></i>
          <h5 class="mt-3 text-muted">У вас пока нет избранных предприятий</h5>
          <p class="text-muted">Добавляйте предприятия в избранное, чтобы быстро находить их</p>
        </div>
      `;
      return;
    }
    
    // Формируем таблицу с избранными
    let html = `
      <div class="table-responsive">
        <table class="table table-hover">
          <thead>
            <tr>
              <th>Название</th>
              <th>Адрес</th>
              <th>Тип лицензии</th>
              <th>Статус</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
    `;
    
    data.favorites.forEach(favorite => {
      const statusClass = favorite.license_status_color === 'expired' ? 'danger' : 
                         favorite.license_status_color === 'expiring_soon' ? 'warning' : 'success';
      
      html += `
        <tr>
          <td>
            <strong>${favorite.object_name || favorite.company_name}</strong>
            <br>
            <small class="text-muted">Добавлено: ${new Date(favorite.added_at).toLocaleDateString()}</small>
          </td>
          <td>${favorite.address || favorite.company_address}</td>
          <td>
            <span class="badge bg-secondary">${favorite.license_type_code}</span>
            <br>
            <small>${favorite.license_type_name}</small>
          </td>
          <td>
            <span class="badge bg-${statusClass}">${favorite.license_status}</span>
            ${favorite.days_until_expire !== null ? 
              `<br><small class="text-muted">${favorite.days_until_expire >= 0 ? 
                `Осталось ${favorite.days_until_expire} дней` : 
                `Просрочено ${Math.abs(favorite.days_until_expire)} дней`}</small>` : ''}
          </td>
          <td>
            <button class="btn btn-sm btn-outline-primary" onclick="showOnMap(${favorite.latitude}, ${favorite.longitude})">
              <i class="bi bi-map"></i> На карте
            </button>
            <button class="btn btn-sm btn-outline-danger" onclick="removeFromFavorites(${favorite.company_id})">
              <i class="bi bi-trash"></i> Удалить
            </button>
          </td>
        </tr>
      `;
    });
    
    html += `
          </tbody>
        </table>
      </div>
    `;
    
    content.innerHTML = html;
    
  } catch (error) {
    console.error('Ошибка при загрузке избранных:', error);
    content.innerHTML = `
      <div class="alert alert-danger">
        <i class="bi bi-exclamation-triangle"></i>
        Ошибка при загрузке избранных предприятий. Попробуйте обновить страницу.
      </div>
    `;
  }
}

function showOnMap(lat, lon) {
  // Закрываем модальное окно
  bootstrap.Modal.getInstance(document.getElementById('favoritesModal')).hide();
  
  // Перемещаем карту к точке
  map.setView([lat, lon], 16);
  
  // Находим и открываем маркер
  markersLayer.eachLayer(marker => {
    const markerLat = marker.getLatLng().lat;
    const markerLon = marker.getLatLng().lng;
    
    if (Math.abs(markerLat - lat) < 0.0001 && Math.abs(markerLon - lon) < 0.0001) {
      marker.openPopup();
    }
  });
}

async function removeFromFavorites(companyId) {
  const token = localStorage.getItem('sessionToken');
  if (!token) return;

  try {
    const response = await fetch(`${API_BASE}/api/favorites/${companyId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });
    
    if (response.ok) {
      showNotification('Предприятие удалено из избранного', 'success');
      updateFavoriteButton(companyId, false);
      updateFavoritesCount();
      showFavorites(); // Обновляем список
    } else {
      showNotification('Ошибка при удалении из избранного', 'error');
    }
  } catch (error) {
    console.error('Ошибка при удалении из избранного:', error);
    showNotification('Ошибка при удалении из избранного', 'error');
  }
}
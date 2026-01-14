// ============================================
// ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ
// ============================================
const API_BASE = "http://127.0.0.1:5000";
let map = null;
let markersLayer = null;
let allCompaniesData = [];

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
  const params = new URLSearchParams();
  params.set("limit", "1000");

  // Собираем фильтры
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
            <button class="btn-sm btn-primary" onclick="findSimilarCompanies(${c.latitude}, ${c.longitude}, '${c.license_type_code}', '${c.inn || ''}')">
              🔍 Поиск похожих (1000м)
            </button>
          </div>
        </div>
      `;
      
      marker.bindPopup(popupHtml, {
        className: "custom-popup",
        maxWidth: 420,
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

    // Обновляем счётчик точек
    document.getElementById("pointsCount").textContent = `${count} точек`;
  } catch (e) {
    console.error(e);
    alert("Ошибка при загрузке данных с backend. Проверь, что Flask запущен.");
  }
}

// ============================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ============================================
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

  // Показываем только похожие предприятия на карте
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
});

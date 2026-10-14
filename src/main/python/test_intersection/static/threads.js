// =============================================================================
// threads.js — таймлайн по потокам.
//
// Что делает:
//   1. Загружает /threads-timeline — события, сгруппированные по потокам.
//   2. Рисует по одной дорожке на поток; бары — события, цвет — по event_type.
//   3. Поиск по name / display_name — подсвечивает совпадения.
//   4. Зум и сдвиг по оси времени — колесо мыши с Shift, перетаскивание с Shift.
//   5. Кнопки предустановленного зума, сброс, инфа о текущем окне.
//
// Ожидаемый JSON от /threads-timeline:
//   {
//     "axis_start_ms": 1234567890000,
//     "axis_end_ms":   1234567995000,
//     "axis_start":    "12:00:00.000",
//     "axis_end":      "12:00:15.000",
//     "ticks":  [ {"left": 0.0, "label": "12:00:00"}, ... ],
//     "threads": [
//       {
//         "name": "ForkJoinPool-1-worker-4",
//         "count": 1200,
//         "events": [
//           {
//             "key":          "event_type:thread:start_time:name",
//             "name":         "spring.boot.application.starting",
//             "display_name": "Spring — application starting",
//             "event_type":   "org.springframework.core.metrics.jfr.FlightRecorderStartupEvent",
//             "left":         12.345,       // % от полной оси
//             "width":        0.5,          // % от полной оси
//             "cls":          "context"     // CSS-класс цвета
//           }, ...
//         ]
//       }, ...
//     ]
//   }
// =============================================================================


// =============================================================================
// Состояние
// =============================================================================

let tlData = null;              // данные из /threads-timeline
let tlZoom = 1.0;               // текущий масштаб (1 = вся ось видна)
let tlOffset = 0.0;             // сдвиг: доля от начала (0..1)
let tlHighlight = "";           // подстрока поиска для подсветки
let tlDragging = false;         // флаг перетаскивания
let tlDragStartX = 0;
let tlDragStartOffset = 0;
let tlRenderScheduled = false;  // защита от слишком частого перерендера

const MIN_ZOOM = 1.0;
const MAX_ZOOM = 5000.0;


// =============================================================================
// Загрузка
// =============================================================================

async function loadThreadsTimeline() {
  const r = await fetch('/threads-timeline');
  if (!r.ok) {
    throw new Error(`/threads-timeline → HTTP ${r.status}`);
  }
  return r.json();
}


// =============================================================================
// Утилиты
// =============================================================================

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[c]));
}

function escapeAttr(s) {
  return escapeHtml(s);
}

/**
 * Проверяет, подходит ли событие под строку поиска.
 * Ищет по display_name и name, регистронезависимо.
 */
function eventMatches(ev, query) {
  if (!query) return false;
  const q = query.toLowerCase();
  return (
    (ev.display_name || '').toLowerCase().includes(q) ||
    (ev.name || '').toLowerCase().includes(q)
  );
}

/**
 * Текст тултипа для бара.
 * Использует только поля JfrEvent: display_name, name, event_type.
 */
function eventTitle(ev) {
  const parts = [];

  const title = ev.display_name || ev.name || '—';
  parts.push(title);

  if (ev.name && ev.name !== ev.display_name) {
    parts.push(`(${ev.name})`);
  }

  if (ev.event_type) {
    parts.push(`type=${ev.event_type}`);
  }

  return parts.join(' ');
}


// =============================================================================
// Проекция координат
//
// В данных left/width — проценты от ПОЛНОЙ оси (0..100).
// При зуме и сдвиге видимая часть оси — это [tlOffset, tlOffset + 1/tlZoom].
//
// screen_pct = (full_pct/100 - tlOffset) / (1/tlZoom) * 100
// =============================================================================

function projectLeft(fullPct) {
  const viewSpan = 1 / tlZoom;
  return ((fullPct / 100 - tlOffset) / viewSpan) * 100;
}

function projectWidth(fullWidthPct) {
  const viewSpan = 1 / tlZoom;
  return (fullWidthPct / 100 / viewSpan) * 100;
}


// =============================================================================
// Рендер
// =============================================================================

function scheduleRender() {
  if (tlRenderScheduled) return;
  tlRenderScheduled = true;
  requestAnimationFrame(() => {
    tlRenderScheduled = false;
    renderThreadsTimeline();
  });
}

function renderThreadsTimeline() {
  if (!tlData) return;

  const threadsEl = document.getElementById('tlThreads');
  const axisEl = document.getElementById('tlAxis');
  if (!threadsEl || !axisEl) return;

  const viewStart = tlOffset;
  const viewEnd = tlOffset + 1 / tlZoom;

  // ---- дорожки ----
  const rowsHtml = tlData.threads.map(thread => {
    const eventsHtml = thread.events.map(ev => {
      const left = projectLeft(ev.left);
      const width = projectWidth(ev.width);

      // Отсекаем бары, полностью улетевшие за пределы видимой части.
      // Небольшой запас (-2%, +102%), чтобы бар не «моргал» на краях.
      if (left + width < -2 || left > 102) return '';

      const isHighlighted = tlHighlight && eventMatches(ev, tlHighlight);
      const cls = `bar ${ev.cls || 'event'}${isHighlighted ? ' highlight' : ''}`;

      return `<div class="${cls}"
                   style="left:${left.toFixed(4)}%;width:${width.toFixed(4)}%"
                   data-key="${escapeAttr(ev.key || '')}"
                   title="${escapeAttr(eventTitle(ev))}"></div>`;
    }).join('');

    return `
      <div class="tl-row">
        <div class="tl-row-label" title="${escapeAttr(thread.name)}">
          ${escapeHtml(thread.name)}
          <span class="threads">${thread.count}</span>
        </div>
        <div class="tl-row-track">
          ${eventsHtml}
        </div>
      </div>
    `;
  }).join('');

  threadsEl.innerHTML = rowsHtml;

  // ---- ось ----
  // Показываем только те засечки, что попали в видимую часть.
  const ticksHtml = (tlData.ticks || []).map(t => {
    const pct = t.left / 100;
    if (pct < viewStart - 0.005 || pct > viewEnd + 0.005) return '';
    const left = projectLeft(t.left);
    return `<span class="tl-axis-label" style="left:${left.toFixed(4)}%">${escapeHtml(t.label)}</span>`;
  }).join('');

  axisEl.innerHTML = `<div class="tl-axis-inner">${ticksHtml}</div>`;
}


// =============================================================================
// Зум
// =============================================================================

/**
 * Устанавливает зум, сохраняя точку focalPct (0..1) на месте.
 *
 * @param {number} newZoom  — новый масштаб, clamp по [MIN_ZOOM, MAX_ZOOM]
 * @param {number} focalPct — позиция фокуса на текущем экране: 0 = левый край, 1 = правый
 */
function setZoom(newZoom, focalPct) {
  newZoom = Math.max(MIN_ZOOM, Math.min(newZoom, MAX_ZOOM));
  focalPct = Math.max(0, Math.min(1, focalPct));

  // точка под фокусом в полной шкале 0..1
  const viewSpan = 1 / tlZoom;
  const focalFull = tlOffset + focalPct * viewSpan;

  // после зума хотим, чтобы та же точка была под тем же местом экрана
  const newViewSpan = 1 / newZoom;
  let newOffset = focalFull - focalPct * newViewSpan;

  // не вылезать за границы
  newOffset = Math.max(0, Math.min(newOffset, 1 - newViewSpan));

  tlZoom = newZoom;
  tlOffset = newOffset;
  scheduleRender();
  updateZoomInfo();
}

function resetZoom() {
  tlZoom = 1;
  tlOffset = 0;
  scheduleRender();
  updateZoomInfo();
}

function updateZoomInfo() {
  const el = document.getElementById('tlZoomInfo');
  if (!el) return;
  const left = (tlOffset * 100).toFixed(2);
  const right = ((tlOffset + 1 / tlZoom) * 100).toFixed(2);
  el.textContent = `×${tlZoom.toFixed(2)}  [${left}% … ${right}%]`;
}


// =============================================================================
// Обработчики
// =============================================================================

function bindSearch() {
  const input = document.getElementById('tlSearch');
  if (!input) return;

  input.addEventListener('input', (e) => {
    tlHighlight = e.target.value.trim();
    scheduleRender();
    if (tlHighlight) scrollToFirstHighlight();
  });
}

/**
 * Прокручивает страницу так, чтобы первый подсвеченный бар был виден.
 * Полезно при поиске с зазумленным таймлайном.
 */
function scrollToFirstHighlight() {
  requestAnimationFrame(() => {
    const el = document.querySelector('#tlThreads .bar.highlight');
    if (!el) return;
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
  });
}

function bindZoomButtons() {
  const z1 = document.getElementById('tlZoom1');
  const z10 = document.getElementById('tlZoom10');
  const z100 = document.getElementById('tlZoom100');
  const reset = document.getElementById('tlZoomReset');

  if (z1) z1.addEventListener('click', () => setZoom(1, 0.5));
  if (z10) z10.addEventListener('click', () => setZoom(10, 0.5));
  if (z100) z100.addEventListener('click', () => setZoom(100, 0.5));
  if (reset) reset.addEventListener('click', resetZoom);
}

function bindWheelZoom() {
  const scroll = document.getElementById('tlScroll');
  if (!scroll) return;

  scroll.addEventListener('wheel', (e) => {
    // Зум — только с Shift. Обычный вертикальный скролл не перехватываем.
    if (!e.shiftKey) return;
    e.preventDefault();

    const rect = scroll.getBoundingClientRect();
    const focalPct = (e.clientX - rect.left) / rect.width;
    const factor = e.deltaY < 0 ? 1.2 : 1 / 1.2;

    setZoom(tlZoom * factor, focalPct);
  }, { passive: false });
}

function bindDragPan() {
  const scroll = document.getElementById('tlScroll');
  if (!scroll) return;

  scroll.addEventListener('mousedown', (e) => {
    // Сдвиг — только с Shift и левой кнопкой.
    if (e.button !== 0 || !e.shiftKey) return;
    e.preventDefault();
    tlDragging = true;
    tlDragStartX = e.clientX;
    tlDragStartOffset = tlOffset;
    scroll.style.cursor = 'grabbing';
  });

  window.addEventListener('mousemove', (e) => {
    if (!tlDragging) return;
    const scrollEl = document.getElementById('tlScroll');
    if (!scrollEl) return;

    const rect = scrollEl.getBoundingClientRect();
    const dx = e.clientX - tlDragStartX;
    const viewSpan = 1 / tlZoom;
    const dOffset = -(dx / rect.width) * viewSpan;

    let newOffset = tlDragStartOffset + dOffset;
    newOffset = Math.max(0, Math.min(newOffset, 1 - viewSpan));

    tlOffset = newOffset;
    scheduleRender();
    updateZoomInfo();
  });

  window.addEventListener('mouseup', () => {
    if (!tlDragging) return;
    tlDragging = false;
    const scrollEl = document.getElementById('tlScroll');
    if (scrollEl) scrollEl.style.cursor = '';
  });
}


// =============================================================================
// Инициализация
// =============================================================================

(async function initThreadsTimeline() {
  const container = document.getElementById('tlThreads');
  if (!container) return;   // страницы с таймлайном нет — молча выходим

  container.innerHTML = '<div class="empty">Загрузка событий...</div>';

  try {
    tlData = await loadThreadsTimeline();
  } catch (e) {
    console.error(e);
    container.innerHTML =
      '<div class="empty">Ошибка загрузки таймлайна: ' +
      escapeHtml(e.message) + '</div>';
    return;
  }

  if (!tlData.threads || !tlData.threads.length) {
    container.innerHTML = '<div class="empty">Нет событий для отображения</div>';
    return;
  }

  bindSearch();
  bindZoomButtons();
  bindWheelZoom();
  bindDragPan();

  renderThreadsTimeline();
  updateZoomInfo();

  console.log(
    'threads timeline:',
    tlData.threads.length, 'потоков,',
    tlData.threads.reduce((n, t) => n + t.count, 0), 'событий',
  );
})();
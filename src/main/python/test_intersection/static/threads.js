// =============================================================================
// threads.js — таймлайн по потокам с зумом, мини-картой и поиском.
//
// Управление:
//   • Колесо мыши над таймлайном     — зум к точке под курсором
//   • Shift + колесо                 — горизонтальная прокрутка
//   • Перетаскивание левой кнопкой   — прокрутка
//   • Клик по мини-карте             — прыжок в это место
//   • Перетаскивание окна мини-карты — плавный сдвиг
//   • Кнопки ×1 / ×10 / ×100         — предустановленный зум к центру
//   • Кнопка «Сбросить»              — вернуть весь диапазон
//   • Поле поиска                    — подсветка + автоскролл к совпадению
// =============================================================================


// ---------- состояние ----------

let tlData = null;              // данные /threads-timeline
let tlZoom = 1.0;               // текущий масштаб (>=1)
let tlOffset = 0.0;             // сдвиг: доля от начала оси (0..1)
let tlHighlight = "";           // подстрока для подсветки
let tlRenderScheduled = false;

const MIN_ZOOM = 1.0;
const MAX_ZOOM = 5000.0;


// ---------- загрузка ----------

async function loadThreadsTimeline() {
  const r = await fetch('/threads-timeline');
  if (!r.ok) throw new Error(`/threads-timeline → HTTP ${r.status}`);
  return r.json();
}


// ---------- утилиты ----------

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}
function escapeAttr(s) { return escapeHtml(s); }

function eventMatches(ev, query) {
  if (!query) return false;
  const q = query.toLowerCase();
  return (
    (ev.display_name || '').toLowerCase().includes(q) ||
    (ev.name         || '').toLowerCase().includes(q)
  );
}

function eventTitle(ev) {
  const parts = [];
  parts.push(ev.display_name || ev.name || '—');
  if (ev.name && ev.name !== ev.display_name) parts.push(`(${ev.name})`);
  if (ev.event_type) parts.push(`type=${ev.event_type}`);
  return parts.join(' ');
}


// ---------- проекция координат ----------
//
// left/width приходят как проценты от полной оси (0..100).
// Видимая часть оси — [tlOffset, tlOffset + 1/tlZoom].
//
// screen_pct = (full_pct/100 - tlOffset) / (1/tlZoom) * 100

function projectLeft(fullPct) {
  const viewSpan = 1 / tlZoom;
  return ((fullPct / 100 - tlOffset) / viewSpan) * 100;
}
function projectWidth(fullWidthPct) {
  const viewSpan = 1 / tlZoom;
  return (fullWidthPct / 100 / viewSpan) * 100;
}


// ---------- рендер ----------

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
  const ticksHtml = (tlData.ticks || []).map(t => {
    const pct = t.left / 100;
    if (pct < viewStart - 0.005 || pct > viewEnd + 0.005) return '';
    const left = projectLeft(t.left);
    return `<span class="tl-axis-label" style="left:${left.toFixed(4)}%">${escapeHtml(t.label)}</span>`;
  }).join('');
  axisEl.innerHTML = `<div class="tl-axis-inner">${ticksHtml}</div>`;

  // ---- мини-карта: обновляем окно ----
  updateOverviewWindow();
}


// ---------- зум ----------

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

function panBy(deltaFraction) {
  const viewSpan = 1 / tlZoom;
  let newOffset = tlOffset + deltaFraction * viewSpan;
  newOffset = Math.max(0, Math.min(newOffset, 1 - viewSpan));
  tlOffset = newOffset;
  scheduleRender();
  updateZoomInfo();
}

function panTo(offset) {
  const viewSpan = 1 / tlZoom;
  tlOffset = Math.max(0, Math.min(offset, 1 - viewSpan));
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


// ---------- мини-карта ----------

function updateOverviewWindow() {
  const w = document.getElementById('tlOverviewWindow');
  if (!w) return;
  const viewSpan = 1 / tlZoom;
  w.style.left  = (tlOffset * 100) + '%';
  w.style.width = (viewSpan * 100) + '%';
}

function bindOverview() {
  const ov = document.getElementById('tlOverview');
  const win = document.getElementById('tlOverviewWindow');
  if (!ov || !win) return;

  // клик по свободному месту мини-карты — прыжок
  ov.addEventListener('click', (e) => {
    if (e.target === win) return;   // клик по окну — это drag, не прыжок
    const rect = ov.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    const viewSpan = 1 / tlZoom;
    panTo(pct - viewSpan / 2);
  });

  // перетаскивание окна
  let dragging = false;
  let startX = 0;
  let startOffset = 0;

  win.addEventListener('mousedown', (e) => {
    e.stopPropagation();
    e.preventDefault();
    dragging = true;
    startX = e.clientX;
    startOffset = tlOffset;
    win.style.cursor = 'grabbing';
  });

  window.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    const rect = ov.getBoundingClientRect();
    const dx = e.clientX - startX;
    const viewSpan = 1 / tlZoom;
    let newOffset = startOffset + dx / rect.width;
    newOffset = Math.max(0, Math.min(newOffset, 1 - viewSpan));
    tlOffset = newOffset;
    scheduleRender();
    updateZoomInfo();
  });

  window.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    win.style.cursor = 'grab';
  });
}


// ---------- геометрия дорожки ----------

/**
 * Прямоугольник дорожки (без подписи слева).
 * Используется и для зума, и для drag-пана, чтобы координаты совпадали.
 */
function trackRect() {
  const anyTrack = document.querySelector('.tl-row-track');
  if (anyTrack) return anyTrack.getBoundingClientRect();
  const scroll = document.getElementById('tlScroll');
  return scroll ? scroll.getBoundingClientRect() : null;
}


// ---------- колесо ----------

function bindWheelZoom() {
  const scroll = document.getElementById('tlScroll');
  if (!scroll) return;

  scroll.addEventListener('wheel', (e) => {
    // Shift + колесо — горизонтальная прокрутка.
    if (e.shiftKey) {
      e.preventDefault();
      const rect = trackRect();
      if (!rect) return;
      const viewSpan = 1 / tlZoom;
      const dPct = (e.deltaY / rect.width) * viewSpan;
      panBy(dPct);
      return;
    }

    // Обычное колесо — зум к точке под курсором.
    e.preventDefault();
    const rect = trackRect();
    if (!rect) return;

    const focalPct = Math.max(0, Math.min(1,
      (e.clientX - rect.left) / rect.width
    ));

    const factor = e.deltaY < 0 ? 1.2 : 1 / 1.2;
    setZoom(tlZoom * factor, focalPct);
  }, { passive: false });
}


// ---------- drag-пан (левая кнопка, без Shift) ----------

function bindDragPan() {
  const scroll = document.getElementById('tlScroll');
  if (!scroll) return;

  let dragging = false;
  let startX = 0;
  let startOffset = 0;

  scroll.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    // Не начинаем drag, если клик по мини-карте или по бару-подсветке.
    if (e.target.closest('.timeline-overview')) return;

    e.preventDefault();
    dragging = true;
    startX = e.clientX;
    startOffset = tlOffset;
    scroll.style.cursor = 'grabbing';
  });

  window.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    const rect = trackRect();
    if (!rect) return;

    const dx = e.clientX - startX;
    const viewSpan = 1 / tlZoom;
    // dx отрицательный → сдвиг вправо (смотрим правую часть оси)
    const dOffset = -(dx / rect.width) * viewSpan;

    let newOffset = startOffset + dOffset;
    newOffset = Math.max(0, Math.min(newOffset, 1 - viewSpan));
    tlOffset = newOffset;
    scheduleRender();
    updateZoomInfo();
  });

  window.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    scroll.style.cursor = '';
  });
}


// ---------- поиск ----------

function bindSearch() {
  const input = document.getElementById('tlSearch');
  if (!input) return;

  input.addEventListener('input', (e) => {
    tlHighlight = e.target.value.trim();
    scheduleRender();
    if (tlHighlight) focusFirstMatch();
  });
}

/**
 * Находит первый подходящий бар, при необходимости подзумивает к нему
 * и прокручивает в видимую часть.
 */
function focusFirstMatch() {
  if (!tlHighlight || !tlData) return;

  // Ищем первое подходящее событие в данных.
  let hit = null;
  for (const thread of tlData.threads) {
    for (const ev of thread.events) {
      if (eventMatches(ev, tlHighlight)) { hit = ev; break; }
    }
    if (hit) break;
  }
  if (!hit) return;

  // Позиция события в долях полной оси.
  const centerPct = (hit.left + hit.width / 2) / 100;
  const viewSpan = 1 / tlZoom;

  // Хотим видеть его примерно на 1/3 экрана — с запасом слева.
  const desiredLeft = 0.33;
  let newOffset = centerPct - desiredLeft * viewSpan;
  newOffset = Math.max(0, Math.min(newOffset, 1 - viewSpan));

  tlOffset = newOffset;
  scheduleRender();
  updateZoomInfo();

  // После рендера проскроллим контейнер к подсвеченному бару.
  requestAnimationFrame(() => {
    const el = document.querySelector('#tlThreads .bar.highlight');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
  });
}


// ---------- кнопки ----------

function bindZoomButtons() {
  const z1 = document.getElementById('tlZoom1');
  const z10 = document.getElementById('tlZoom10');
  const z100 = document.getElementById('tlZoom100');
  const reset = document.getElementById('tlZoomReset');
  const toStart = document.getElementById('tlToStart');
  const toEnd = document.getElementById('tlToEnd');

  if (z1) z1.addEventListener('click', () => setZoom(1, 0.5));
  if (z10) z10.addEventListener('click', () => setZoom(10, 0.5));
  if (z100) z100.addEventListener('click', () => setZoom(100, 0.5));
  if (reset) reset.addEventListener('click', resetZoom);
  if (toStart) toStart.addEventListener('click', () => panTo(0));
  if (toEnd) toEnd.addEventListener('click', () => panTo(1));
}


// ---------- инициализация ----------

(async function initThreadsTimeline() {
  const container = document.getElementById('tlThreads');
  if (!container) return;

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
  bindOverview();

  renderThreadsTimeline();
  updateZoomInfo();

  console.log(
    'threads timeline:',
    tlData.threads.length, 'потоков,',
    tlData.threads.reduce((n, t) => n + t.count, 0), 'событий',
  );
})();
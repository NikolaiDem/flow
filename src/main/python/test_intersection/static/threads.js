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
  return ev.name;
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


// ---------- засечки и сетка ----------

/**
 * Округляет шаг до ближайшего «красивого» значения:
 * 1 мс, 2 мс, 5 мс, 10 мс, 20 мс, 50 мс, 100 мс, 200 мс, 500 мс,
 * 1 с, 2 с, 5 с, 10 с, 30 с, 1 мин, 5 мин, 15 мин, 1 ч и т.д.
 */
function niceStep(ms) {
  if (ms <= 0) return 1;
  const exp = Math.floor(Math.log10(ms));
  const base = Math.pow(10, exp);
  const norm = ms / base;
  let mult;
  if (norm < 1.5) mult = 1;
  else if (norm < 3.5) mult = 2;
  else if (norm < 7.5) mult = 5;
  else mult = 10;
  return mult * base;
}

/**
 * Форматирует метку времени с точностью, соответствующей шагу.
 */
function formatTime(dt, stepMs) {
  const hh = String(dt.getHours()).padStart(2, '0');
  const mm = String(dt.getMinutes()).padStart(2, '0');
  const ss = String(dt.getSeconds()).padStart(2, '0');
  const ms = String(dt.getMilliseconds()).padStart(3, '0');

  if (stepMs < 1000) {
    return `${hh}:${mm}:${ss}.${ms}`;
  }
  if (stepMs < 60_000) {
    return `${hh}:${mm}:${ss}`;
  }
  return `${hh}:${mm}`;
}

/**
 * Генерирует засечки для текущего состояния зума.
 * Чем больше tlZoom, тем мельче шаг и точнее подписи.
 *
 * @param {number} axisStartMs
 * @param {number} axisEndMs
 * @param {number} maxTicks — верхний предел, чтобы не забить DOM
 * @returns {Array<{left: number, label: string}>}
 */
function makeTicksForZoom(axisStartMs, axisEndMs, maxTicks = 200) {
  const span = Math.max(axisEndMs - axisStartMs, 1);
  const viewSpan = 1 / tlZoom;
  const viewStartMs = axisStartMs + tlOffset * span;
  const viewEndMs = viewStartMs + viewSpan * span;

  // Ширина трека в пикселях — от неё зависит, сколько подписей влезет.
  const track = document.querySelector('.tl-row-track');
  const trackWidth = track ? track.getBoundingClientRect().width : 800;

  // Минимальное расстояние между подписями (в пикселях).
  const MIN_LABEL_GAP_PX = 80;

  // Сколько засечек максимум влезает на видимую часть.
  const maxVisible = Math.max(2, Math.floor(trackWidth / MIN_LABEL_GAP_PX));

  // Базовый шаг по времени: целимся в maxVisible засечек.
  let stepMs = niceStep((viewEndMs - viewStartMs) / maxVisible);

  // Если подписи всё равно не влезают (например, формат слишком длинный),
  // увеличиваем шаг в 2 раза, пока не влезем.
  // Здесь эмпирика: длина подписи ~7 символов × 7 px ≈ 50 px.
  const labelPx = 60;
  while ((trackWidth / ((viewEndMs - viewStartMs) / stepMs)) < labelPx && stepMs < span) {
    stepMs *= 2;
    stepMs = niceStep(stepMs);
  }

  const t0 = Math.ceil(viewStartMs / stepMs) * stepMs;
  const result = [];
  for (let t = t0; t <= viewEndMs && result.length < maxTicks; t += stepMs) {
    const left = ((t - axisStartMs) / span) * 100;
    result.push({ left, label: formatTime(new Date(t), stepMs) });
  }
  return result;
}

/**
 * Рисует вертикальные линии сетки поверх всех дорожек.
 * Принимает засечки, посчитанные на фронте под текущий зум.
 */
function renderGrid(ticks) {
  const gridEl = document.getElementById('tlGrid');
  if (!gridEl) return;

  gridEl.innerHTML = (ticks || []).map((t, i) => {
    const left = projectLeft(t.left);
    const isMajor = (i % 5 === 0) || (i === ticks.length - 1);

    return `<div class="tl-grid-line${isMajor ? ' major' : ''}"
                 style="left:${left.toFixed(4)}%"></div>`;
  }).join('');
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

  // ---- засечки (генерируются на фронте под текущий зум) ----
  const ticks = makeTicksForZoom(tlData.axis_start_ms, tlData.axis_end_ms);

  // ---- ось ----
  const ticksHtml = ticks.map(t => {
    const left = projectLeft(t.left);
    return `<span class="tl-axis-label" style="left:${left.toFixed(4)}%">${escapeHtml(t.label)}</span>`;
  }).join('');
  axisEl.innerHTML = `<div class="tl-axis-inner">${ticksHtml}</div>`;

  // ---- вертикальная сетка (те же ticks, что и ось) ----
  renderGrid(ticks);

  // ---- мини-карта ----
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
    // Не начинаем drag, если клик по мини-карте или по бару.
    if (e.target.closest('.timeline-overview')) return;
    if (e.target.closest('.bar')) return;

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

  let hit = null;
  for (const thread of tlData.threads) {
    for (const ev of thread.events) {
      if (eventMatches(ev, tlHighlight)) { hit = ev; break; }
    }
    if (hit) break;
  }
  if (!hit) return;

  const centerPct = (hit.left + hit.width / 2) / 100;
  const viewSpan = 1 / tlZoom;

  const desiredLeft = 0.33;
  let newOffset = centerPct - desiredLeft * viewSpan;
  newOffset = Math.max(0, Math.min(newOffset, 1 - viewSpan));

  tlOffset = newOffset;
  scheduleRender();
  updateZoomInfo();

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
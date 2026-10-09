// =============================================================================
// app.js — фронтенд таймлайна пересечений тестов.
//
// Секции страницы (см. index.html):
//   1) Поиск одного теста          → GET  /search?q=...
//   2) Групповой таймлайн тестов   → POST /group-timeline  {keys}
//   3) Таймлайн событий            → POST /mixed-timeline {event_types}
//
// Вспомогательные эндпоинты:
//   GET /all-tests     — плоский список тестов для мультиселекта
//   GET /event-types   — список {event_type, count} для чекбоксов
//
// Общий принцип: каждая секция независима. Ошибки одной не ломают другие.
// =============================================================================


// =============================================================================
// Общие утилиты
// =============================================================================

/**
 * Экранирование для безопасной вставки в innerHTML.
 *
 * Зачем нужно: данные приходят с бэкенда (display_name, class_name и т.п.)
 * и могут содержать <, >, &, кавычки. Если вставить их «как есть» — получим
 * XSS или сломанную разметку. Всегда пропускаем через escapeHtml перед вставкой.
 *
 * null/undefined превращаем в пустую строку, чтобы не получить "null" в UI.
 */
function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

/** То же для значений атрибутов (data-key, title). */
function escapeAttr(s) {
  return escapeHtml(s);
}

/**
 * CSS-класс для статуса теста.
 *
 * Используется и как класс бейджа (<span class="status passed">),
 * и как класс бара (<div class="bar failed">).
 *
 * Правила:
 *   PASSED / SUCCESS / SUCCESSFUL → "passed"  (зелёный)
 *   FAILED / FAILURE / ERROR      → "failed"  (красный)
 *   всё остальное                 → "other"   (серый)
 */
function statusClass(result) {
  const r = String(result || '').toUpperCase();
  if (r === 'PASSED' || r === 'SUCCESS' || r === 'SUCCESSFUL') return 'passed';
  if (r === 'FAILED' || r === 'FAILURE' || r === 'ERROR') return 'failed';
  return 'other';
}

/**
 * Человекочитаемая подпись теста.
 *
 * "Class.method", либо одна из частей, либо name, если ни class_name,
 * ни method_name не заполнены. Используется в мультиселекте и тегах.
 */
function testLabel(t) {
  const cls = t.class_name || '';
  const mth = t.method_name || '';
  if (cls && mth) return `${cls}.${mth}`;
  if (mth) return mth;
  if (cls) return cls;
  return t.name || '';
}

/**
 * Вертикальные засечки внутри дорожки (без подписей).
 *
 * ticks — массив {left: 0..100, label: "HH:MM:SS"} с бэкенда.
 * Каждая 5-я и последняя засечки получают класс "major" (чуть темнее в CSS).
 *
 * pointer-events: none в CSS — мышь проходит сквозь линии, тултипы баров работают.
 */
function renderTicks(ticks) {
  if (!ticks || !ticks.length) return '';
  const last = ticks.length - 1;
  return ticks.map((t, i) => {
    const major = (i % 5 === 0) || (i === last);
    return `<div class="tick${major ? ' major' : ''}" style="left:${t.left}%"></div>`;
  }).join('');
}

/**
 * Единый слой подписей засечек под таймлайном.
 *
 * Рисуется один раз на карточку, а не в каждой строке — так подписи
 * не дублируются и не мешают барам.
 *
 * Крайние подписи прижимаются к краям через transform:
 *   i=0        → translateX(0)     (левая подпись не уезжает влево)
 *   i=last     → translateX(-100%) (правая не уезжает вправо)
 *   остальные  → translateX(-50%)  (центрируем по засечке)
 */
function renderTicksAxis(ticks) {
  if (!ticks || !ticks.length) return '';
  const last = ticks.length - 1;
  return `
    <div class="ticks-axis">
      ${ticks.map((t, i) => {
        const major = (i % 5 === 0) || (i === last);
        if (!major) return '';
        const anchor =
          i === 0 ? 'translateX(0)' :
          i === last ? 'translateX(-100%)' :
          'translateX(-50%)';
        return `<span class="ticks-axis-label" style="left:${t.left}%; transform:${anchor}">
          ${escapeHtml(t.label)}
        </span>`;
      }).join('')}
    </div>
  `;
}


// =============================================================================
// Глобальное состояние
// =============================================================================

/**
 * allTests — плоский список всех тестов из /all-tests.
 * Используется обеими фабриками мультиселекта (секция 2 и, потенциально, 3).
 * Заполняется один раз в loadAllTests().
 */
let allTests = [];

/**
 * eventTypesAll — [{event_type: "org.junit.TestExecution", count: 9}, ...]
 * из /event-types. Используется для рендера чекбоксов в секции 3.
 */
const eventTypesAll = [];

/**
 * selectedEventTypes — Set выбранных event_type (значения чекбоксов).
 * Активность кнопки «Построить таймлайн событий» зависит от его размера.
 */
const selectedEventTypes = new Set();

/**
 * Загрузка списка тестов.
 *
 * Проверяем, что пришёл массив — иначе UI будет падать на allTests.filter.
 * При ошибке ставим пустой массив: дропдаун покажет «Тесты не загружены»,
 * остальная страница продолжит работать.
 */
async function loadAllTests() {
  try {
    const r = await fetch('/all-tests');
    const data = await r.json();
    if (!Array.isArray(data)) {
      console.error('/all-tests: ожидался массив, пришло:', data);
      allTests = [];
      return;
    }
    allTests = data;
    console.log('Загружено тестов:', allTests.length);
  } catch (e) {
    console.error('Ошибка загрузки /all-tests:', e);
    allTests = [];
  }
}

/**
 * Загрузка типов событий для чекбоксов секции 3.
 *
 * Формат: [{event_type, count}, ...] — count для подписи "N шт." справа.
 * Если сервер вернул не массив — не трогаем eventTypesAll.
 */
async function loadEventTypes() {
  try {
    const r = await fetch('/event-types');
    const data = await r.json();
    if (!Array.isArray(data)) {
      console.error('/event-types: ожидался массив, пришло:', data);
      return;
    }
    eventTypesAll.length = 0;
    eventTypesAll.push(...data);
    console.log('Загружено типов событий:', eventTypesAll.length);
  } catch (e) {
    console.error('Ошибка загрузки /event-types:', e);
  }
}


// =============================================================================
// Секция 1. Поиск одного теста
//
// Пользователь печатает в #q. С дебаунсом 150 мс летит GET /search?q=...
// Бэкенд возвращает массив карточек: [{key, class_name, method_name, thread,
// result, rows, partners, ticks, axis_start, axis_end}, ...].
// =============================================================================

const q = document.getElementById('q');
const results = document.getElementById('results');
let searchTimer = null;

// Дебаунс: не отправлять запрос на каждый набранный символ.
// Ждём 150 мс тишины после последнего нажатия — тогда searchOne().
q.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(searchOne, 150);
});

/**
 * Запрос к /search и рендер результатов.
 * Пустой запрос очищает результаты без обращения к серверу.
 */
async function searchOne() {
  const query = q.value.trim();
  if (!query) { results.innerHTML = ''; return; }
  try {
    const r = await fetch('/search?q=' + encodeURIComponent(query));
    const data = await r.json();
    renderSearchResults(data);
  } catch (e) {
    results.innerHTML = '<div class="empty">Ошибка: ' + escapeHtml(e.message) + '</div>';
  }
}

/**
 * Рендер карточек поиска.
 *
 * Каждая карточка:
 *   - шапка (.name): "Class.method  name [thread]  PASSED"
 *   - таймлайн: строки с барами (искомый тест сверху + его партнёры)
 *   - axis: подписи засечек под дорожками
 *   - список партнёров: name [thread] status — X ms
 *
 * Если партнёров нет — показываем "Пересечений не найдено".
 * Всё, что приходит из данных, проходит через escapeHtml.
 */
function renderSearchResults(items) {
  if (!items.length) {
    results.innerHTML = '<div class="empty">Ничего не найдено</div>';
    return;
  }
  results.innerHTML = items.map(item => `
    <div class="item" data-key="${escapeAttr(item.key || '')}">
      <div class="name">
        <span>${escapeHtml(item.class_name)}.${escapeHtml(item.method_name)}</span>
        <span class="threads">${escapeHtml(item.name)} [${escapeHtml(item.thread)}]</span>
        <span class="status ${statusClass(item.result)}">${escapeHtml(item.result)}</span>
      </div>

      <div class="timeline">
        ${item.rows.map(r => `
          <div class="row">
            <div class="row-label" title="${escapeAttr(r.title)}">
              ${escapeHtml(r.class_name)}.${escapeHtml(r.method_name)}
              <span class="threads">${escapeHtml(r.name)} [${escapeHtml(r.thread)}]</span>
            </div>
            <div class="row-track">
              ${renderTicks(item.ticks)}
              <div class="bar ${r.cls}"
                   style="left:${r.left}%; width:${r.width}%"
                   title="${escapeAttr(r.title)}"></div>
            </div>
          </div>
        `).join('')}
      </div>
      ${renderTicksAxis(item.ticks)}

      ${item.partners.length === 0
        ? '<div class="pair"><span class="other" style="color:#999">Пересечений не найдено</span></div>'
        : item.partners.map(p => `
        <div class="pair">
          <span class="other">
            ${escapeHtml(p.class_name)}.${escapeHtml(p.method_name)}
            <span class="threads">${escapeHtml(p.other)} [${escapeHtml(p.thread)}]</span>
            <span class="status ${statusClass(p.result)}">${escapeHtml(p.result)}</span>
          </span>
          <span class="ms">${p.ms.toFixed(1)} ms</span>
        </div>
      `).join('')}
    </div>
  `).join('');
}


// =============================================================================
// Фабрика мультиселекта тестов
//
// Создаёт изолированный компонент: дропдаун с чекбоксами + теги + кнопка
// «Построить» + контейнер таймлайна. Секция 2 использует один экземпляр,
// при желании можно создать второй (например, для смешанного таймлайна).
//
// Каждый экземпляр держит своё состояние в замыкании:
//   - selected — Set выбранных ключей (t.key == tc.name)
//   - visible  — тесты, прошедшие текущий фильтр поиска
// =============================================================================

function createMultiSelect(cfg) {
  const {
    inputEl, dropdownEl, searchEl, optionsEl,   // элементы дропдауна
    tagsEl,                                     // контейнер тегов выбранных
    buildBtnEl, timelineEl,                     // кнопка и контейнер результата
    buildUrl,                                   // '/group-timeline' и т.п.
    minSelected,                                // минимум выбранных для активации кнопки
    extraPayload,                               // () => ({...}) — доп. поля в POST-тело
    extraValid,                                 // () => bool — доп. условие активности
    titleText,                                  // заголовок над таймлайном
  } = cfg;

  // Внутреннее состояние компонента.
  const selected = new Set();
  let visible = [];

  // ---- Дропдаун ----

  // Клик по полю-«кнопке» переключает .open и уводит фокус в поле поиска.
  // stopPropagation — чтобы document.click не закрыл дропдаун сразу же.
  inputEl.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdownEl.classList.toggle('open');
    if (dropdownEl.classList.contains('open')) searchEl.focus();
  });

  // Клик по полю поиска не должен закрывать дропдаун.
  searchEl.addEventListener('click', (e) => e.stopPropagation());

  // Фильтрация опций по мере ввода.
  searchEl.addEventListener('input', () => renderOptions(searchEl.value));

  // ---- Рендер списка опций ----

  /**
   * Рисует список тестов с учётом фильтра.
   *
   * Фильтр — регистронезависимая подстрока по name, class_name, method_name,
   * thread и по склейке "Class.method".
   *
   * После innerHTML обработчики теряются — поэтому навешиваем их заново
   * на каждую .multi-select-option.
   */
  function renderOptions(filter = '') {
    const lower = filter.toLowerCase();
    visible = allTests.filter(t => {
      if (!lower) return true;
      return (
        (t.name || '').toLowerCase().includes(lower) ||
        (t.class_name || '').toLowerCase().includes(lower) ||
        (t.method_name || '').toLowerCase().includes(lower) ||
        (t.thread || '').toLowerCase().includes(lower) ||
        `${t.class_name || ''}.${t.method_name || ''}`.toLowerCase().includes(lower)
      );
    });

    if (!allTests.length) {
      optionsEl.innerHTML = '<div class="multi-select-option" style="color:#c62828;cursor:default">Тесты не загружены</div>';
      return;
    }
    if (!visible.length) {
      optionsEl.innerHTML = '<div class="multi-select-option" style="color:#999;cursor:default">Ничего не найдено</div>';
      return;
    }

    optionsEl.innerHTML = visible.map(t => `
      <div class="multi-select-option" data-key="${escapeAttr(t.key)}">
        <input type="checkbox" ${selected.has(t.key) ? 'checked' : ''}>
        <span>${escapeHtml(testLabel(t))}</span>
        <span class="threads">${escapeHtml(t.name || '')}</span>
        <span class="threads">[${escapeHtml(t.thread || '')}]</span>
        <span class="status ${statusClass(t.result)}">${escapeHtml(t.result || '')}</span>
      </div>
    `).join('');

    // Переподключаем обработчики после перерисовки.
    optionsEl.querySelectorAll('.multi-select-option[data-key]').forEach(opt => {
      opt.addEventListener('click', (e) => {
        e.stopPropagation();
        const key = opt.dataset.key;
        if (selected.has(key)) selected.delete(key);
        else selected.add(key);
        // После изменения выбора — перерисовать всё, что зависит от selected.
        renderOptions(searchEl.value);
        renderTags();
        updateButton();
      });
    });
  }

  // ---- Теги выбранных ----

  /**
   * Рендер тегов выбранных тестов под дропдауном.
   * Каждый тег — плашка с крестиком для удаления.
   */
  function renderTags() {
    tagsEl.innerHTML = Array.from(selected).map(key => {
      const t = allTests.find(x => x.key === key);
      const text = t ? testLabel(t) : key;
      return `
        <span class="selected-tag">
          ${escapeHtml(text)}
          <button data-remove="${escapeAttr(key)}">&times;</button>
        </span>
      `;
    }).join('');

    tagsEl.querySelectorAll('button[data-remove]').forEach(btn => {
      btn.addEventListener('click', () => remove(btn.dataset.remove));
    });
  }

  /** Удаление теста из выбранных (по крестику в теге). */
  function remove(key) {
    selected.delete(key);
    renderOptions(searchEl.value);
    renderTags();
    updateButton();
  }

  // ---- Активность кнопки «Построить» ----

  /**
   * Кнопка активна, если:
   *   - выбрано минимум minSelected тестов;
   *   - extraValid() === true (если он задан).
   *
   * Например, для группы тестов minSelected = 2.
   */
  function updateButton() {
    const enoughSelected = selected.size >= minSelected;
    const extra = extraValid ? extraValid() : true;
    buildBtnEl.disabled = !(enoughSelected && extra);
  }

  // ---- Массовые действия ----

  /** «Выбрать все видимые» — все, что сейчас в списке после фильтра. */
  function selectAllVisible() {
    visible.forEach(t => selected.add(t.key));
    renderOptions(searchEl.value);
    renderTags();
    updateButton();
  }

  /** «Очистить» — сбросить всё выбранное. */
  function clearAll() {
    selected.clear();
    renderOptions(searchEl.value);
    renderTags();
    updateButton();
  }

  // ---- Отправка запроса ----

  /**
   * Собирает payload и делает POST на buildUrl.
   *
   * Всегда кладём keys и test_keys (для совместимости с /group-timeline
   * и /mixed-timeline), плюс extraPayload() — например, event_types.
   *
   * Пока идёт запрос — показываем плейсхолдер «Строим таймлайн...».
   * Если кнопка disabled — не отправляем (защита от повторных кликов).
   */
  async function build() {
    if (buildBtnEl.disabled) {
      console.warn('build: кнопка disabled, запрос не отправлен');
      return;
    }

    const payload = {
      keys: Array.from(selected),
      test_keys: Array.from(selected),
      ...(extraPayload ? extraPayload() : {}),
    };

    timelineEl.innerHTML = '<div class="empty">Строим таймлайн...</div>';
    try {
      const r = await fetch(buildUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      renderTimeline(data);
    } catch (e) {
      timelineEl.innerHTML = '<div class="empty">Ошибка: ' + escapeHtml(e.message) + '</div>';
    }
  }

  // ---- Рендер результата ----

  /**
   * Рендер таймлайна тестов.
   *
   * Формат строк (из test_timeline.make_row):
   *   {key, name, class_name, method_name, thread, result,
   *    cls, left, width, title}
   *
   * Плюс общий data.ticks для шкалы.
   */
  function renderTimeline(data) {
    if (!data.rows || !data.rows.length) {
      timelineEl.innerHTML = '<div class="empty">Нет данных для отображения</div>';
      return;
    }

    timelineEl.innerHTML = `
      <div class="item" style="margin-top:1rem">
        <div class="name">${escapeHtml(titleText)} (${data.rows.length} шт.)</div>
        <div class="timeline">
          ${data.rows.map(r => renderRow(r, data.ticks)).join('')}
        </div>
        ${renderTicksAxis(data.ticks)}
      </div>
    `;
  }

  /**
   * Одна строка таймлайна теста.
   * Подпись: "Class.method  name [thread]".
   * Бар: absolute-элемент с left/width в процентах, класс r.cls (passed/failed/other).
   */
  function renderRow(r, ticks) {
    const labelHtml = `${escapeHtml(r.class_name)}.${escapeHtml(r.method_name)}`;
    const subHtml = `<span class="threads">${escapeHtml(r.name)} [${escapeHtml(r.thread)}]</span>`;

    return `
      <div class="row">
        <div class="row-label" title="${escapeAttr(r.title)}">
          ${labelHtml}
          ${subHtml}
        </div>
        <div class="row-track">
          ${renderTicks(ticks)}
          <div class="bar ${r.cls}"
               style="left:${r.left}%; width:${r.width}%"
               title="${escapeAttr(r.title)}"></div>
        </div>
      </div>
    `;
  }

  // Публичный интерфейс компонента (наружу отдаём только это).
  return {
    renderOptions,
    renderTags,
    updateButton,
    selectAllVisible,
    clearAll,
    build,
    get selected() { return selected; },
  };
}


// =============================================================================
// Секция 2. Групповой таймлайн тестов
//
// Один экземпляр createMultiSelect:
//   - источник — allTests (заполняется loadAllTests)
//   - buildUrl — /group-timeline
//   - minSelected = 2 (для группы нужно минимум 2 теста)
// =============================================================================

const groupMulti = createMultiSelect({
  inputEl:    document.getElementById('groupInput'),
  dropdownEl: document.getElementById('groupDropdown'),
  searchEl:   document.getElementById('groupSearch'),
  optionsEl:  document.getElementById('groupOptions'),
  tagsEl:     document.getElementById('selectedTags'),
  buildBtnEl: document.getElementById('buildBtn'),
  timelineEl: document.getElementById('groupTimeline'),
  buildUrl:   '/group-timeline',
  minSelected: 2,
  titleText:  'Таймлайн группы тестов',
});

// Кнопки массовых действий и построения.
document.getElementById('selectAllBtn')
  .addEventListener('click', () => groupMulti.selectAllVisible());
document.getElementById('clearAllBtn')
  .addEventListener('click', () => groupMulti.clearAll());
document.getElementById('buildBtn')
  .addEventListener('click', () => groupMulti.build());


// =============================================================================
// Секция 3. Таймлайн событий (только JfrEvent)
//
// Работает по выбранным event_type. Мультиселект тестов в этой секции
// не используется: рендер идёт по всем событиям подходящих типов, без
// объединения с тестами.
//
// Формат строк (из events_timeline.make_row):
//   {key, name, display_name, thread, event_type, cls, left, width, title}
// =============================================================================

const eventsTimelineEl = document.getElementById('mixedTimeline');
const eventsBuildBtn = document.getElementById('mixedBuildBtn');

/**
 * Рендер таймлайна событий.
 *
 * Единый шаблон: "display_name [thread] event_type".
 * Никаких class_name/method_name/result — их в этой модели нет.
 */
function renderEventTimeline(data) {
  if (!data.rows || !data.rows.length) {
    eventsTimelineEl.innerHTML = '<div class="empty">Нет данных для отображения</div>';
    return;
  }

  eventsTimelineEl.innerHTML = `
    <div class="item" style="margin-top:1rem">
      <div class="name">Таймлайн событий (${data.rows.length} шт.)</div>
      <div class="timeline">
        ${data.rows.map(r => `
          <div class="row">
            <div class="row-label" title="${escapeAttr(r.title)}">
              ${escapeHtml(r.display_name || r.name || '')}
              <span class="threads">[${escapeHtml(r.thread || '')}]</span>
              <span class="threads">${escapeHtml(r.event_type || '')}</span>
            </div>
            <div class="row-track">
              ${renderTicks(data.ticks)}
              <div class="bar ${r.cls}"
                   style="left:${r.left}%; width:${r.width}%"
                   title="${escapeAttr(r.title)}"></div>
            </div>
          </div>
        `).join('')}
      </div>
      ${renderTicksAxis(data.ticks)}
    </div>
  `;
}

/**
 * Отправка POST /mixed-timeline с выбранными event_types.
 *
 * Кнопка активна только когда есть хотя бы один выбранный тип
 * (см. updateEventBuildBtn). Здесь — дополнительная защита.
 */
async function buildEventTimeline() {
  const types = Array.from(selectedEventTypes);
  if (!types.length) {
    console.warn('buildEventTimeline: не выбрано ни одного типа события');
    return;
  }

  eventsTimelineEl.innerHTML = '<div class="empty">Строим таймлайн...</div>';
  try {
    const r = await fetch('/mixed-timeline', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ event_types: types }),
    });
    const data = await r.json();
    renderEventTimeline(data);
  } catch (e) {
    eventsTimelineEl.innerHTML = '<div class="empty">Ошибка: ' + escapeHtml(e.message) + '</div>';
  }
}

eventsBuildBtn.addEventListener('click', buildEventTimeline);


// =============================================================================
// Чекбоксы типов событий (секция 3)
//
// eventTypesAll      — заполняется из /event-types
// selectedEventTypes — Set выбранных типов
// #mixedBuildBtn активна, если selectedEventTypes.size > 0
// =============================================================================

const eventTypesList = document.getElementById('eventTypesList');
const eventTypesAllBtn = document.getElementById('eventTypesAllBtn');
const eventTypesNoneBtn = document.getElementById('eventTypesNoneBtn');

/** Кнопка «Построить таймлайн событий» активна, если выбран хоть один тип. */
function updateEventBuildBtn() {
  eventsBuildBtn.disabled = selectedEventTypes.size === 0;
}

/**
 * Рендер списка чекбоксов типов событий.
 *
 * Формат строки:
 *   <label>
 *     <input type="checkbox" value="org.junit.TestExecution">
 *     <span>org.junit.TestExecution</span>
 *     <span class="count">9</span>
 *   </label>
 *
 * После innerHTML обработчики навешиваются заново.
 * Клик по чекбоксу добавляет/удаляет значение из selectedEventTypes
 * и обновляет активность кнопки.
 */
function renderEventTypes() {
  if (!eventTypesAll.length) {
    eventTypesList.innerHTML = '<div class="empty">Типов событий не найдено</div>';
    return;
  }
  eventTypesList.innerHTML = eventTypesAll.map(et => `
    <label>
      <input type="checkbox" value="${escapeAttr(et.event_type)}"
             ${selectedEventTypes.has(et.event_type) ? 'checked' : ''}>
      <span>${escapeHtml(et.event_type)}</span>
      <span class="count">${et.count}</span>
    </label>
  `).join('');

  eventTypesList.querySelectorAll('input[type="checkbox"]').forEach(cb => {
    cb.addEventListener('change', () => {
      if (cb.checked) selectedEventTypes.add(cb.value);
      else selectedEventTypes.delete(cb.value);
      updateEventBuildBtn();
    });
  });
}

// «Все» — отметить все типы и перерисовать список.
eventTypesAllBtn.addEventListener('click', () => {
  eventTypesAll.forEach(et => selectedEventTypes.add(et.event_type));
  renderEventTypes();
  updateEventBuildBtn();
});

// «Ничего» — снять все типы.
eventTypesNoneBtn.addEventListener('click', () => {
  selectedEventTypes.clear();
  renderEventTypes();
  updateEventBuildBtn();
});


// =============================================================================
// Закрытие дропдауна по клику вне .multi-select
//
// Единый обработчик на document. Если клик вне .multi-select — закрываем
// дропдаун секции 2. Других активных дропдаунов сейчас нет.
// =============================================================================

document.addEventListener('click', (e) => {
  if (!e.target.closest('.multi-select')) {
    document.getElementById('groupDropdown').classList.remove('open');
  }
});


// =============================================================================
// Инициализация
//
// Порядок:
//   1) Параллельно грузим тесты и типы событий.
//   2) Рисуем опции мультиселекта (иначе дропдаун будет пустым).
//   3) Рисуем чекбоксы типов событий.
//   4) Обновляем состояние обеих кнопок по фактическому состоянию.
// =============================================================================

(async function init() {
  await Promise.all([loadAllTests(), loadEventTypes()]);

  groupMulti.renderOptions();
  renderEventTypes();
  groupMulti.updateButton();
  updateEventBuildBtn();
})();
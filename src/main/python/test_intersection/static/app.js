// =============================================================================
// Общие утилиты
// =============================================================================

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

function escapeAttr(s) {
  return escapeHtml(s);
}

function statusClass(result) {
  const r = String(result || '').toUpperCase();
  if (r === 'PASSED' || r === 'SUCCESS' || r === 'SUCCESSFUL') return 'passed';
  if (r === 'FAILED' || r === 'FAILURE' || r === 'ERROR') return 'failed';
  return 'other';
}

function testLabel(t) {
  const cls = t.class_name || '';
  const mth = t.method_name || '';
  if (cls && mth) return `${cls}.${mth}`;
  if (mth) return mth;
  if (cls) return cls;
  return t.name || '';
}

function renderTicks(ticks) {
  if (!ticks || !ticks.length) return '';
  const last = ticks.length - 1;
  return ticks.map((t, i) => {
    const major = (i % 5 === 0) || (i === last);
    return `<div class="tick${major ? ' major' : ''}" style="left:${t.left}%"></div>`;
  }).join('');
}

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

let allTests = [];                       // заполняется loadAllTests()
const eventTypesAll = [];                // [{event_type, count}, ...]
const selectedEventTypes = new Set();

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
// =============================================================================

const q = document.getElementById('q');
const results = document.getElementById('results');
let searchTimer = null;

q.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(searchOne, 150);
});

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
// Фабрика мультиселекта
// =============================================================================

function createMultiSelect(cfg) {
  const {
    inputEl, dropdownEl, searchEl, optionsEl,
    tagsEl, buildBtnEl, timelineEl,
    buildUrl,                 // '/group-timeline' | '/mixed-timeline'
    minSelected,              // 2 для группы; 0 для mixed
    extraPayload,             // () => ({ event_types: [...] }) для mixed
    extraValid,               // () => bool — доп. условие активности кнопки
    titleText,                // заголовок при рендере таймлайна
    rowFormat,                // 'test' | 'event' — как рисовать подпись строки
  } = cfg;

  const selected = new Set();
  let visible = [];

  // ---- дропдаун ----
  inputEl.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdownEl.classList.toggle('open');
    if (dropdownEl.classList.contains('open')) searchEl.focus();
  });
  searchEl.addEventListener('click', (e) => e.stopPropagation());
  searchEl.addEventListener('input', () => renderOptions(searchEl.value));

  // ---- опции ----
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

    optionsEl.querySelectorAll('.multi-select-option[data-key]').forEach(opt => {
      opt.addEventListener('click', (e) => {
        e.stopPropagation();
        const key = opt.dataset.key;
        if (selected.has(key)) selected.delete(key);
        else selected.add(key);
        renderOptions(searchEl.value);
        renderTags();
        updateButton();
      });
    });
  }

  // ---- теги ----
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

  function remove(key) {
    selected.delete(key);
    renderOptions(searchEl.value);
    renderTags();
    updateButton();
  }

  // ---- активность кнопки ----
  function updateButton() {
    const enoughSelected = selected.size >= minSelected;
    const extra = extraValid ? extraValid() : true;
    buildBtnEl.disabled = !(enoughSelected && extra);
  }

  // ---- массовые действия ----
  function selectAllVisible() {
    visible.forEach(t => selected.add(t.key));
    renderOptions(searchEl.value);
    renderTags();
    updateButton();
  }

  function clearAll() {
    selected.clear();
    renderOptions(searchEl.value);
    renderTags();
    updateButton();
  }

  // ---- отправка ----
  async function build() {
    if (buildBtnEl.disabled) {
      console.warn('build: кнопка disabled, запрос не отправлен');
      return;
    }

    const payload = {
      keys: Array.from(selected),        // /group-timeline
      test_keys: Array.from(selected),   // /mixed-timeline
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

  // ---- рендер таймлайна ----
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

  // ---- одна строка ----
  function renderRow(r, ticks) {
    let labelHtml;
    let subHtml;

    if (rowFormat === 'test') {
      // секция 2: только тесты, есть class_name/method_name/result
      labelHtml = `${escapeHtml(r.class_name)}.${escapeHtml(r.method_name)}`;
      subHtml = `<span class="threads">${escapeHtml(r.name)} [${escapeHtml(r.thread)}]</span>`;
    } else {
      // секция 3: единый формат JfrEvent — только display_name/event_type/thread
      labelHtml = `${escapeHtml(r.display_name || r.name || '')}`;
      subHtml = `
        <span class="threads">[${escapeHtml(r.thread || '')}]</span>
        <span class="threads">${escapeHtml(r.event_type || '')}</span>
      `;
    }

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
  rowFormat:  'test',
});

document.getElementById('selectAllBtn')
  .addEventListener('click', () => groupMulti.selectAllVisible());
document.getElementById('clearAllBtn')
  .addEventListener('click', () => groupMulti.clearAll());

// =============================================================================
// Секция 3. Смешанный таймлайн: тесты + типы событий
// =============================================================================

const mixedMulti = createMultiSelect({
  inputEl:    document.getElementById('mixedTestsInput'),
  dropdownEl: document.getElementById('mixedTestsDropdown'),
  searchEl:   document.getElementById('mixedTestsSearch'),
  optionsEl:  document.getElementById('mixedTestsOptions'),
  tagsEl:     document.getElementById('mixedSelectedTags'),
  buildBtnEl: document.getElementById('mixedBuildBtn'),
  timelineEl: document.getElementById('mixedTimeline'),
  buildUrl:   '/mixed-timeline',
  minSelected: 0,
  extraValid: () => selectedEventTypes.size > 0 || mixedMulti.selected.size > 0,
  extraPayload: () => ({ event_types: Array.from(selectedEventTypes) }),
  titleText:  'Смешанный таймлайн (тесты + события)',
  rowFormat:  'event',
});

document.getElementById('mixedSelectAllBtn')
  .addEventListener('click', () => mixedMulti.selectAllVisible());
document.getElementById('mixedClearAllBtn')
  .addEventListener('click', () => mixedMulti.clearAll());

// =============================================================================
// Чекбоксы типов событий
// =============================================================================

const eventTypesList = document.getElementById('eventTypesList');
const eventTypesAllBtn = document.getElementById('eventTypesAllBtn');
const eventTypesNoneBtn = document.getElementById('eventTypesNoneBtn');

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
      mixedMulti.updateButton();
    });
  });
}

eventTypesAllBtn.addEventListener('click', () => {
  eventTypesAll.forEach(et => selectedEventTypes.add(et.event_type));
  renderEventTypes();
  mixedMulti.updateButton();
});

eventTypesNoneBtn.addEventListener('click', () => {
  selectedEventTypes.clear();
  renderEventTypes();
  mixedMulti.updateButton();
});

// =============================================================================
// Закрытие дропдаунов по клику вне
// =============================================================================

document.addEventListener('click', (e) => {
  if (!e.target.closest('.multi-select')) {
    document.getElementById('groupDropdown').classList.remove('open');
    document.getElementById('mixedTestsDropdown').classList.remove('open');
  }
});

// =============================================================================
// Инициализация
// =============================================================================

(async function init() {
  await Promise.all([loadAllTests(), loadEventTypes()]);

  groupMulti.renderOptions();
  mixedMulti.renderOptions();
  renderEventTypes();
  groupMulti.updateButton();
  mixedMulti.updateButton();
})();
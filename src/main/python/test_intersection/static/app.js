const q = document.getElementById('q');
const results = document.getElementById('results');
const groupInput = document.getElementById('groupInput');
const groupDropdown = document.getElementById('groupDropdown');
const groupSearch = document.getElementById('groupSearch');
const groupOptions = document.getElementById('groupOptions');
const selectedTags = document.getElementById('selectedTags');
const buildBtn = document.getElementById('buildBtn');
const groupTimeline = document.getElementById('groupTimeline');
const selectAllBtn = document.getElementById('selectAllBtn');
const clearAllBtn = document.getElementById('clearAllBtn');

let timer = null;
let allTests = [];
let selectedTests = new Set();   // хранит КЛЮЧИ (t.key)
let visibleTests = [];

q.addEventListener('input', () => {
  clearTimeout(timer);
  timer = setTimeout(search, 150);
});

async function loadAllTests() {
  try {
    const r = await fetch('/all-tests');
    allTests = await r.json();
    console.log('Загружено тестов:', allTests.length);
    renderGroupOptions();
  } catch (e) {
    console.error('Ошибка загрузки списка тестов:', e);
  }
}

groupInput.addEventListener('click', (e) => {
  e.stopPropagation();
  groupDropdown.classList.toggle('open');
  if (groupDropdown.classList.contains('open')) {
    groupSearch.focus();
  }
});

document.addEventListener('click', (e) => {
  if (!e.target.closest('.multi-select')) {
    groupDropdown.classList.remove('open');
  }
});

groupSearch.addEventListener('input', () => {
  renderGroupOptions(groupSearch.value);
});

groupSearch.addEventListener('click', (e) => e.stopPropagation());

// ---------- утилиты ----------

function label(t) {
  const cls = t.class_name || '';
  const mth = t.method_name || '';
  if (cls && mth) return `${cls}.${mth}`;
  if (mth) return mth;
  if (cls) return cls;
  return t.name || '';
}

function findByKey(key) {
  return allTests.find(t => t.key === key);
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

// ---------- мультиселект ----------

function renderGroupOptions(filter = '') {
  const lowerFilter = filter.toLowerCase();
  visibleTests = allTests.filter(t => {
    if (!lowerFilter) return true;
    return (
      (t.name || '').toLowerCase().includes(lowerFilter) ||
      (t.class_name || '').toLowerCase().includes(lowerFilter) ||
      (t.method_name || '').toLowerCase().includes(lowerFilter) ||
      (t.thread || '').toLowerCase().includes(lowerFilter) ||
      `${t.class_name || ''}.${t.method_name || ''}`.toLowerCase().includes(lowerFilter)
    );
  });

  if (!visibleTests.length) {
    groupOptions.innerHTML = '<div class="multi-select-option" style="color:#999;cursor:default">Ничего не найдено</div>';
    return;
  }

  groupOptions.innerHTML = visibleTests.map(t => `
    <div class="multi-select-option" data-key="${escapeAttr(t.key)}">
      <input type="checkbox" ${selectedTests.has(t.key) ? 'checked' : ''}>
      <span>${escapeHtml(label(t))}</span>
      <span class="threads">${escapeHtml(t.name || '')}</span>
      <span class="threads">[${escapeHtml(t.thread || '')}]</span>
      <span class="status ${statusClass(t.result)}">${escapeHtml(t.result || '')}</span>
    </div>
  `).join('');

  groupOptions.querySelectorAll('.multi-select-option[data-key]').forEach(opt => {
    opt.addEventListener('click', (e) => {
      e.stopPropagation();
      const key = opt.dataset.key;
      if (selectedTests.has(key)) {
        selectedTests.delete(key);
      } else {
        selectedTests.add(key);
      }
      renderGroupOptions(groupSearch.value);
      renderSelectedTags();
      updateBuildBtn();
    });
  });
}

function renderSelectedTags() {
  selectedTags.innerHTML = Array.from(selectedTests).map(key => {
    const t = findByKey(key);
    const text = t ? label(t) : key;
    return `
      <span class="selected-tag">
        ${escapeHtml(text)}
        <button data-remove="${escapeAttr(key)}">&times;</button>
      </span>
    `;
  }).join('');

  selectedTags.querySelectorAll('button[data-remove]').forEach(btn => {
    btn.addEventListener('click', () => removeTest(btn.dataset.remove));
  });
}

function removeTest(key) {
  selectedTests.delete(key);
  renderGroupOptions(groupSearch.value);
  renderSelectedTags();
  updateBuildBtn();
}

function updateBuildBtn() {
  buildBtn.disabled = selectedTests.size < 2;
}

selectAllBtn.addEventListener('click', () => {
  visibleTests.forEach(t => selectedTests.add(t.key));
  renderGroupOptions(groupSearch.value);
  renderSelectedTags();
  updateBuildBtn();
});

clearAllBtn.addEventListener('click', () => {
  selectedTests.clear();
  renderGroupOptions(groupSearch.value);
  renderSelectedTags();
  updateBuildBtn();
});

buildBtn.addEventListener('click', async () => {
  if (selectedTests.size < 2) return;

  const keys = Array.from(selectedTests);
  groupTimeline.innerHTML = '<div class="empty">Строим таймлайн...</div>';
  try {
    const r = await fetch('/group-timeline', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ keys })
    });
    const data = await r.json();
    renderGroupTimeline(data);
  } catch (e) {
    groupTimeline.innerHTML = '<div class="empty">Ошибка: ' + escapeHtml(e.message) + '</div>';
  }
});

// ---------- рендер таймлайнов ----------

function renderGroupTimeline(data) {
  if (!data.rows || !data.rows.length) {
    groupTimeline.innerHTML = '<div class="empty">Нет данных для отображения</div>';
    return;
  }

  groupTimeline.innerHTML = `
    <div class="item" style="margin-top:1rem">
      <div class="name">Таймлайн группы тестов (${data.rows.length} шт.)</div>
      <div class="timeline">
        ${data.rows.map(r => `
          <div class="row">
            <div class="row-label" title="${escapeAttr(r.title)}">
              ${escapeHtml(r.class_name)}.${escapeHtml(r.method_name)}
              <span class="threads">${escapeHtml(r.name)} [${escapeHtml(r.thread)}]</span>
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

// ---------- поиск одиночного теста ----------

async function search() {
  const query = q.value.trim();
  if (!query) { results.innerHTML = ''; return; }
  const r = await fetch('/search?q=' + encodeURIComponent(query));
  const data = await r.json();
  render(data);
}

function statusClass(result) {
  const r = String(result || '').toUpperCase();
  if (r === 'PASSED' || r === 'SUCCESS' || r === 'SUCCESSFUL') return 'passed';
  if (r === 'FAILED' || r === 'FAILURE' || r === 'ERROR') return 'failed';
  return 'other';
}

function render(items) {
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

// ---------- esc ----------

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

function escapeAttr(s) {
  return escapeHtml(s);
}

// Загружаем список тестов при старте
loadAllTests();
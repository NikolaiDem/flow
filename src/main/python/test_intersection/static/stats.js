async function loadStats() {
    const r = await fetch('/test-stats');
    return r.json();
}

function fmtSec(s) {
    if (s == null) return '—';
    if (s < 1) return `${(s * 1000).toFixed(0)} мс`;
    if (s < 60) return `${s.toFixed(2)} с`;
    const m = Math.floor(s / 60);
    const sec = (s - m * 60).toFixed(1);
    return `${m}:${sec.padStart(4, '0')} мин`;
}

function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

function renderSummary(data) {
    const el = document.getElementById('summary');
    const ds = data.durations_summary || {};
    el.innerHTML = `
    <div class="stat-card"><span class="label">Всего тестов</span>
      <span class="value">${data.total}</span></div>
    <div class="stat-card"><span class="label">Success rate</span>
      <span class="value">${(data.success_rate * 100).toFixed(1)}%</span></div>
    <div class="stat-card"><span class="label">Суммарное время</span>
      <span class="value">${fmtSec(ds.sum_s)}</span></div>
    <div class="stat-card"><span class="label">Среднее</span>
      <span class="value">${fmtSec(ds.mean_s)}</span></div>
    <div class="stat-card"><span class="label">Медиана</span>
      <span class="value">${fmtSec(ds.median_s)}</span></div>
    <div class="stat-card"><span class="label">p90</span>
      <span class="value">${fmtSec(ds.p90_s)}</span></div>
    <div class="stat-card"><span class="label">p99</span>
      <span class="value">${fmtSec(ds.p99_s)}</span></div>
    <div class="stat-card"><span class="label">Max</span>
      <span class="value">${fmtSec(ds.max_s)}</span></div>
  `;
}

function renderHistogram(canvasId, bins, options = {}) {
    const labels = bins.map(b =>
        options.log
            ? `${b.lo.toPrecision(3)}–${b.hi.toPrecision(3)}`
            : `${b.lo.toFixed(2)}–${b.hi.toFixed(2)}`
    );
    const counts = bins.map(b => b.count);

    new Chart(document.getElementById(canvasId), {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Количество тестов',
                data: counts,
                backgroundColor: options.color || '#4a90d9',
                borderColor: 'white',
                borderWidth: 0.5,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {display: false},
                tooltip: {
                    callbacks: {
                        title: items => `Интервал: ${items[0].label} с`,
                        label: item => `Тестов: ${item.parsed.y}`
                    }
                }
            },
            scales: {
                x: {
                    title: {display: true, text: 'Длительность, с'},
                    ticks: {maxRotation: 60, minRotation: 60, autoSkip: true, font: {size: 10}}
                },
                y: {title: {display: true, text: 'Количество тестов'}, beginAtZero: true}
            }
        }
    });
}

function renderThreadsChart(threads) {
    const labels = threads.map(t => t.name);
    new Chart(document.getElementById('threadsChart'), {
        type: 'bar',
        data: {
            labels,
            datasets: [
                {
                    label: 'Суммарное время тестов, с',
                    data: threads.map(t => t.total_time_s),
                    backgroundColor: '#4a90d9'
                },
                {
                    label: 'Wall-clock потока, с',
                    data: threads.map(t => t.wall_s),
                    backgroundColor: '#b9c3cd'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: {position: 'top'},
                tooltip: {
                    callbacks: {
                        label: item => `${item.dataset.label}: ${item.parsed.x.toFixed(1)} с`
                    }
                }
            },
            scales: {
                x: {title: {display: true, text: 'Секунды'}, beginAtZero: true}
            }
        }
    });
}

function renderThreadsTable(threads) {
    const el = document.getElementById('threadsTable');
    el.innerHTML = `
    <h3>Потоки (таблица)</h3>
    <table class="stats-table">
      <thead>
        <tr>
          <th>Поток</th><th>Тестов</th><th>Упало</th>
          <th>Сумма, с</th><th>Wall, с</th>
          <th>Сред, с</th><th>Медиана, с</th>
          <th>Min, с</th><th>Max, с</th>
        </tr>
      </thead>
      <tbody>
        ${threads.map(t => `
          <tr>
            <td class="mono">${escapeHtml(t.name)}</td>
            <td>${t.total}</td>
            <td>${t.failed}</td>
            <td>${t.total_time_s.toFixed(2)}</td>
            <td>${t.wall_s.toFixed(2)}</td>
            <td>${t.mean_s.toFixed(3)}</td>
            <td>${t.median_s.toFixed(3)}</td>
            <td>${t.min_s.toFixed(3)}</td>
            <td>${t.max_s.toFixed(3)}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function renderCdf(canvasId, cdf) {
    if (!cdf || !cdf.length) return;

    const data = cdf.map(p => ({x: p.t, y: p.count}));

    new Chart(document.getElementById(canvasId), {
        type: 'line',
        data: {
            datasets: [{
                label: 'Тестов с длительностью ≤ X',
                data,
                borderColor: '#3f8fdc',
                backgroundColor: 'rgba(63, 143, 220, .15)',
                borderWidth: 2,
                fill: true,
                pointRadius: 0,
                stepped: 'before',     // ← ключевая опция
                tension: 0,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            parsing: false,        // data уже {x, y}
            plugins: {
                legend: {display: false},
                tooltip: {
                    callbacks: {
                        title: items => `Длительность ≤ ${items[0].parsed.x.toFixed(3)} с`,
                        label: item => {
                            const p = cdf[item.dataIndex];
                            return `Тестов: ${p.count} (${p.pct.toFixed(2)}%)`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'linear',
                    title: {display: true, text: 'Длительность теста, с'},
                    beginAtZero: true,
                    // Максимум — максимальная длительность из данных.
                    max: cdf[cdf.length - 1].t,
                },
                y: {
                    type: 'linear',
                    title: {display: true, text: 'Количество тестов'},
                    beginAtZero: true,
                    max: cdf[cdf.length - 1].count,
                }
            }
        }
    });
}

(async function init() {
    const data = await loadStats();
    renderSummary(data);
    renderHistogram('histLinear', data.hist_linear, {color: '#4a90d9'});
    renderHistogram('histLog', data.hist_log, {color: '#7bb86f', log: true});
    renderThreadsChart(data.by_thread);
    renderThreadsTable(data.by_thread);
    renderCdf('cdfChart', data.cdf);
})();
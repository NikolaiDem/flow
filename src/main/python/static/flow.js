// flow.js — секция Flow: список графов + iframe + fullscreen
(function () {
  const select = document.getElementById("flowSelect");
  const frame  = document.getElementById("flowFrame");
  const empty  = document.getElementById("flowEmpty");
  const status = document.getElementById("flowStatus");
  const reload = document.getElementById("flowReload");
  const fsBtn  = document.getElementById("flowFullscreen");

  // ---------- выбор графа ----------

  function selectItem(url) {
    frame.src = url;
  }

  // ---------- загрузка списка ----------

  async function loadFlowList() {
    status.textContent = "Загрузка…";
    empty.hidden = true;
    try {
      const r = await fetch("/flow-list");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const items = await r.json();

      // сохранить текущий выбор, чтобы не сбрасывать при reload
      const prevUrl = select.value || null;

      select.innerHTML = "";
      if (!items.length) {
        empty.hidden = false;
        frame.src = "about:blank";
        status.textContent = "";
        return;
      }

      items.forEach((it) => {
        const o = document.createElement("option");
        o.value = it.url;
        o.textContent = it.name;
        select.appendChild(o);
      });

      // восстановить выбор, если он ещё существует; иначе — первый
      const urls = items.map(it => it.url);
      if (prevUrl && urls.includes(prevUrl)) {
        select.value = prevUrl;
        selectItem(prevUrl);
      } else {
        selectItem(items[0].url);
      }

      status.textContent = `${items.length} граф(ов)`;
    } catch (e) {
      status.textContent = "Ошибка загрузки";
      empty.hidden = false;
      console.error(e);
    }
  }

  // ---------- события ----------

  select.addEventListener("change", () => {
    selectItem(select.value);
  });

  reload.addEventListener("click", loadFlowList);

  // ---------- fullscreen ----------

  fsBtn.addEventListener("click", () => {
    if (!document.fullscreenElement) {
      frame.requestFullscreen().catch(err => {
        console.error("fullscreen failed:", err);
        status.textContent = "Fullscreen недоступен";
      });
    } else {
      document.exitFullscreen();
    }
  });

  // Обновлять иконку при входе/выходе (в т.ч. по Esc)
  document.addEventListener("fullscreenchange", () => {
    const on = !!document.fullscreenElement;
    fsBtn.textContent = on ? "⤡" : "⛶";
    fsBtn.title = on ? "Выйти из полноэкранного" : "На весь экран";
  });

  // ---------- старт ----------

  loadFlowList();
})();
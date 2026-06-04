// Dashboard: faz polling de /api/state a cada 1s e redesenha a interface.
// Os gráficos usam Chart.js (carregado via CDN no index.html).

let chartUtil = null;
let chartPods = null;
let lastWorkers = null;   // últimos dados, para reconstruir os gráficos ao trocar de tema

// Paletas dos gráficos por tema (clássico Win2000 x escuro/moderno).
const PALETTES = {
  win2000: {
    cpu: "#000080", mem: "#008080", disk: "#808000",
    pods: ["#000080", "#808000", "#008080", "#800080", "#800000"],
    podBorder: "#ffffff", text: "#000000", grid: "#a0a0a0", font: "Tahoma",
  },
  modern: {
    cpu: "#38bdf8", mem: "#a855f7", disk: "#f59e0b",
    pods: ["#38bdf8", "#f59e0b", "#22c55e", "#a855f7", "#ef4444"],
    podBorder: "#1e293b", text: "#e2e8f0", grid: "#334155", font: '"Segoe UI", sans-serif',
  },
};
const currentTheme = () => document.body.classList.contains("theme-modern") ? "modern" : "win2000";
const palette = () => PALETTES[currentTheme()];

// ----------------------------------------------------------- helpers de DOM
const el = (id) => document.getElementById(id);

function barHtml(label, uso, total, pct, classe, unidade) {
  const hot = pct >= 85 ? " hot" : "";
  return `
    <div class="bar">
      <div class="bar-top"><span>${label}</span><span>${uso}/${total}${unidade} · ${pct}%</span></div>
      <div class="track"><div class="fill ${classe}${hot}" style="width:${Math.min(pct,100)}%"></div></div>
    </div>`;
}

function workerCard(w) {
  const u = w.utilizacao;
  const pods = w.pods.length
    ? w.pods.map(p => `<span class="podchip" style="background:${p.cor}" title="cpu ${p.cpu_req} · mem ${p.mem_req}MB · disco ${p.disk_req}GB">${p.nome}</span>`).join("")
    : `<span class="wpods-empty">sem PODs</span>`;
  return `
    <div class="worker">
      <div class="worker-head">
        <span class="wname">${w.nome}</span>
        <span class="wlat">⏱ ${w.latency} ms</span>
      </div>
      ${barHtml("CPU", w.cpu_uso, w.cpu_total, u.cpu, "cpu", "")}
      ${barHtml("Memória", w.mem_uso, w.mem_total, u.mem, "mem", "MB")}
      ${barHtml("Disco", w.disk_uso, w.disk_total, u.disk, "disk", "GB")}
      <div class="wpods">${pods}</div>
    </div>`;
}

function kpi(num, lbl, cls) {
  return `<div class="kpi ${cls||""}"><div class="num">${num}</div><div class="lbl">${lbl}</div></div>`;
}

// ----------------------------------------------------------- render principal
function render(state) {
  el("schedBadge").textContent = "⚙ " + state.scheduler;

  const r = state.resumo;
  el("kpis").innerHTML =
    kpi(r.criados, "PODs criados", "accent") +
    kpi(r.na_fila, "Na fila", "warn") +
    kpi(r.executando, "Executando", "good") +
    kpi(r.concluidos, "Concluídos", "") +
    kpi(r.nao_alocaveis, "Não alocáveis", r.nao_alocaveis ? "bad" : "") +
    kpi(state.workers.length, "Workers", "accent");

  el("queue").innerHTML = state.fila.length
    ? state.fila.map(n => `<span class="qchip">${n}</span>`).join("")
    : `<span class="wpods-empty">fila vazia</span>`;

  el("workers").innerHTML = state.workers.map(workerCard).join("");
  el("log").innerHTML = state.eventos.map(e => `<li>${e}</li>`).join("");

  updateCharts(state.workers);
}

// ----------------------------------------------------------- gráficos
function updateCharts(workers) {
  lastWorkers = workers;
  const p = palette();
  const nomes = workers.map(w => w.nome);
  const cpu = workers.map(w => w.utilizacao.cpu);
  const mem = workers.map(w => w.utilizacao.mem);
  const disk = workers.map(w => w.utilizacao.disk);
  const nPods = workers.map(w => w.pods.length);

  if (!chartUtil) {
    chartUtil = new Chart(el("chartUtil"), {
      type: "bar",
      data: { labels: nomes, datasets: [
        { label: "CPU %",     data: cpu,  backgroundColor: p.cpu },
        { label: "Memória %", data: mem,  backgroundColor: p.mem },
        { label: "Disco %",   data: disk, backgroundColor: p.disk },
      ]},
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { title: { display: true, text: "Utilização por Worker (%)", color: p.text, font: { family: p.font } },
                   legend: { labels: { color: p.text, font: { family: p.font } } } },
        scales: { y: { beginAtZero: true, max: 100, ticks: { color: p.text }, grid: { color: p.grid } },
                  x: { ticks: { color: p.text }, grid: { display: false } } },
      }
    });
  } else {
    chartUtil.data.labels = nomes;
    chartUtil.data.datasets[0].data = cpu;
    chartUtil.data.datasets[1].data = mem;
    chartUtil.data.datasets[2].data = disk;
    chartUtil.update("none");
  }

  if (!chartPods) {
    chartPods = new Chart(el("chartPods"), {
      type: "doughnut",
      data: { labels: nomes, datasets: [{ data: nPods,
        backgroundColor: p.pods, borderColor: p.podBorder, borderWidth: 2 }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { title: { display: true, text: "PODs por Worker", color: p.text, font: { family: p.font } },
                   legend: { position: "bottom", labels: { color: p.text, font: { family: p.font } } } },
      }
    });
  } else {
    chartPods.data.labels = nomes;
    chartPods.data.datasets[0].data = nPods;
    chartPods.update("none");
  }
}

// ----------------------------------------------------------- comparação
function cmpCard(res, isWin, notaWin) {
  return `
    <div class="cmp-card ${isWin ? "win" : ""}">
      <h3>${res.scheduler} ${isWin ? `<span class="tag-win">★ ${notaWin}</span>` : ""}</h3>
      <div class="cmp-row"><span>PODs alocados</span><b>${res.alocados}</b></div>
      <div class="cmp-row"><span>Não alocáveis</span><b>${res.nao_alocaveis}</b></div>
      <div class="cmp-row"><span>Balanceamento (desvio, menor=melhor)</span><b>${res.balanceamento_stddev}</b></div>
      <div class="cmp-row"><span>Latência média ponderada (ms)</span><b>${res.latencia_media_ponderada}</b></div>
    </div>`;
}

async function rodarComparacao() {
  const btn = el("btnCompare");
  btn.disabled = true; btn.textContent = "Calculando...";
  try {
    const c = await (await fetch("/api/compare")).json();
    const p = c.proposto, d = c.padrao;
    const propBalanceMelhor = p.balanceamento_stddev <= d.balanceamento_stddev;
    const propLatMelhor = p.latencia_media_ponderada <= d.latencia_media_ponderada;
    el("compareResult").innerHTML = `
      <div class="cmp-grid">
        ${cmpCard(p, true, "proposto")}
        ${cmpCard(d, false, "")}
      </div>
      <p class="cmp-note">
        Mesma carga de <b>${c.n_pods} PODs</b> submetida aos dois escalonadores, partindo de Workers idênticos.
        O escalonador <b>proposto</b> usa 4 métricas (CPU, memória, disco e latência), enquanto o
        <b>padrão do Kubernetes</b> decide apenas por CPU e memória.
        ${propLatMelhor ? "✔ O proposto obteve <b>menor latência média</b> para os PODs sensíveis a rede. " : ""}
        ${propBalanceMelhor ? "✔ O proposto <b>balanceou melhor</b> a carga entre os Workers." : ""}
      </p>`;
  } catch (e) {
    el("compareResult").innerHTML = `<span class="muted">Erro ao comparar: ${e}</span>`;
  } finally {
    btn.disabled = false; btn.textContent = "⚖️ Comparar proposto × padrão";
  }
}

// ----------------------------------------------------------- troca de tema
// Recria os gráficos para que adotem a paleta do tema atual.
function rebuildCharts() {
  if (chartUtil) { chartUtil.destroy(); chartUtil = null; }
  if (chartPods) { chartPods.destroy(); chartPods = null; }
  if (lastWorkers) updateCharts(lastWorkers);
}

function applyTheme(tema) {
  document.body.classList.toggle("theme-modern", tema === "modern");
  const btn = el("themeToggle");
  if (btn) btn.textContent = tema === "modern" ? "🖥️ Tema clássico" : "🌙 Tema escuro";
  localStorage.setItem("minikube-theme", tema);
  rebuildCharts();
}

// ----------------------------------------------------------- relógio da taskbar
function updateClock() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  el("clock").textContent = `${hh}:${mm}`;
}

// ----------------------------------------------------------- loop de polling
async function tick() {
  try {
    const state = await (await fetch("/api/state")).json();
    render(state);
  } catch (e) { /* servidor ainda subindo */ }
}

el("btnCompare").addEventListener("click", rodarComparacao);

// tema: aplica o salvo (padrão = clássico Win2000) e liga o botão da taskbar
applyTheme(localStorage.getItem("minikube-theme") || "win2000");
el("themeToggle").addEventListener("click", () =>
  applyTheme(currentTheme() === "modern" ? "win2000" : "modern"));

updateClock();
setInterval(updateClock, 1000);
tick();
setInterval(tick, 1000);

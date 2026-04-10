/**
 * DIANA-Nexus Desktop — Real-time UI Logic
 *
 * Handles: real-time component updates, P2P log feed,
 * window management (terminal, files, settings), taskbar,
 * and backend API integration.
 *
 * Author: Sahidh — DIANA Architecture
 */

(function () {
  "use strict";

  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return document.querySelectorAll(sel); }

  // ─── Clock ───
  function updateClock() {
    const now = new Date();
    const h = String(now.getHours()).padStart(2, "0");
    const m = String(now.getMinutes()).padStart(2, "0");
    const s = String(now.getSeconds()).padStart(2, "0");
    const el = $("#clock");
    if (el) el.textContent = `${h}:${m}:${s}`;
  }
  setInterval(updateClock, 1000);
  updateClock();

  // ─── Window Management ───
  window.toggleWindow = function(id) {
    const win = document.getElementById(id);
    if (!win) return;
    if (win.style.display === "none" || !win.style.display) {
      win.style.display = "flex";
    } else {
      win.style.display = "none";
    }
  };

  // Topbar button handlers
  const btnTerminal = $("#btn-terminal");
  const btnFiles = $("#btn-files");
  const btnSettings = $("#btn-settings");
  if (btnTerminal) btnTerminal.addEventListener("click", () => toggleWindow("terminal-window"));
  if (btnFiles) btnFiles.addEventListener("click", () => toggleWindow("files-window"));
  if (btnSettings) btnSettings.addEventListener("click", () => toggleWindow("settings-window"));

  // ─── Terminal Emulation ───
  const termInput = $("#terminal-input");
  const termBody = $("#terminal-body");

  const COMMANDS = {
    help: "Available commands: help, uname, cat /proc/diana/stats, cat /proc/diana/p2p_log, uptime, clear, ls, diana-status, neofetch",
    uname: "DIANA-Nexus Kernel 1.0.0-diana-nexus (x86_64) — SYNAPSE Architecture",
    uptime: () => `up ${Math.floor(performance.now()/60000)} min, load: 0.01, 0.02, 0.00`,
    ls: "bin  boot  dev  etc  proc  sys  tmp  usr  var",
    "ls /proc/diana": "stats  hints  p2p_log  cpu_report",
    "cat /proc/diana/stats": () => [
      "╔═══════════════════════════════════════════╗",
      "║    DIANA-Nexus — SYNAPSE Chip Statistics   ║",
      "╚═══════════════════════════════════════════╝",
      "",
      "[RAM SYNAPSE]",
      `  patterns_learned: ${globalState.patterns.RAM}`,
      `  predictions: ${globalState.predictions.RAM}`,
      `  accuracy: ${globalState.confidence.RAM.toFixed(0)}%`,
      "",
      "[GPU SYNAPSE]",
      `  patterns_learned: ${globalState.patterns.GPU}`,
      `  predictions: ${globalState.predictions.GPU}`,
      `  accuracy: ${globalState.confidence.GPU.toFixed(0)}%`,
      "",
      "[SSD SYNAPSE]",
      `  patterns_learned: ${globalState.patterns.SSD}`,
      `  predictions: ${globalState.predictions.SSD}`,
      `  accuracy: ${globalState.confidence.SSD.toFixed(0)}%`,
      "",
      "[CACHE SYNAPSE]",
      `  patterns_learned: ${globalState.patterns.CACHE}`,
      `  predictions: ${globalState.predictions.CACHE}`,
      `  accuracy: ${globalState.confidence.CACHE.toFixed(0)}%`,
      "",
      "[CPU OBSERVER]",
      "  commands_issued: 0",
      `  status_updates_received: ${globalState.cycle * 4}`,
    ].join("\n"),
    "cat /proc/diana/p2p_log": "=== DIANA P2P Bus Log ===\nRAM → GPU : PREFETCH_REQUEST payload=0x4000\nSSD → CACHE : DATA_READY payload=0x1000\nCACHE → RAM : ACK payload=0x0",
    "diana-status": () => `DIANA-Nexus v1.0 — Cycle ${globalState.cycle}\nComponents: RAM ✓ GPU ✓ SSD ✓ CACHE ✓\nCPU: Passive Observer (0 commands)\nP2P Bus: ${globalState.p2pCount} messages\nLearning: Active (${globalState.cycle} cycles completed)`,
    neofetch: [
      "  ✦ DIANA-Nexus OS v1.0",
      "  ─────────────────────",
      "  Kernel: DIANA-Nexus 1.0.0-synapse",
      "  Architecture: x86_64 (SYNAPSE P2P)",
      "  CPU Role: Passive Observer",
      "  Components: RAM, GPU, SSD, CACHE",
      "  Intelligence: LSTM + Q-Learning RL",
      "  P2P Bus: Active (spinlock-protected)",
      "  Shell: diana-sh 1.0",
      "  Theme: Glassmorphism Dark",
    ].join("\n"),
    clear: "__CLEAR__",
  };

  if (termInput) {
    termInput.addEventListener("keydown", function(e) {
      if (e.key === "Enter") {
        const cmd = this.value.trim();
        this.value = "";
        if (!cmd) return;

        // Show the command in terminal
        const cmdDiv = document.createElement("div");
        cmdDiv.innerHTML = `<span class="term-prompt">root@diana-nexus:~#</span> ${cmd}`;
        termBody.appendChild(cmdDiv);

        // Execute
        let output = COMMANDS[cmd];
        if (typeof output === "function") output = output();

        if (output === "__CLEAR__") {
          termBody.innerHTML = "";
        } else if (output) {
          const outDiv = document.createElement("div");
          outDiv.className = "term-output";
          outDiv.textContent = output;
          outDiv.style.whiteSpace = "pre";
          termBody.appendChild(outDiv);
        } else {
          const errDiv = document.createElement("div");
          errDiv.className = "term-error";
          errDiv.textContent = `diana-sh: command not found: ${cmd}`;
          termBody.appendChild(errDiv);
        }

        termBody.scrollTop = termBody.scrollHeight;
      }
    });
  }

  // ─── Global State ───
  const globalState = {
    cycle: 0,
    p2pCount: 0,
    confidence: { RAM: 85, GPU: 92, SSD: 78, CACHE: 99 },
    patterns: { RAM: 0, GPU: 0, SSD: 0, CACHE: 0 },
    predictions: { RAM: 0, GPU: 0, SSD: 0, CACHE: 0 },
  };

  const COMPONENTS = ["RAM", "GPU", "SSD", "CACHE"];
  const P2P_MESSAGES = [
    { from: "RAM", to: "GPU", msg: "VRAM Texture Swapped via DMA" },
    { from: "SSD", to: "CACHE", msg: "Inode Table Pushed (LSTM Prefetch)" },
    { from: "GPU", to: "RAM", msg: "Compute Buffer Released" },
    { from: "CACHE", to: "SSD", msg: "Eviction Notice — 32KB freed" },
    { from: "RAM", to: "SSD", msg: "Sequential Read Predicted (conf: 94%)" },
    { from: "GPU", to: "CACHE", msg: "Shader Cache Warm — 128KB" },
    { from: "SSD", to: "RAM", msg: "Block Prefetch Complete (4 pages)" },
    { from: "CACHE", to: "GPU", msg: "Texture Cache Hit — DMA direct" },
    { from: "RAM", to: "CACHE", msg: "Page Fault Pattern Learned" },
    { from: "SSD", to: "GPU", msg: "Model Weights Loaded via P2P" },
  ];
  const AI_ACTIONS = {
    RAM: [
      "Prefetching next texture block...",
      "Learning page fault sequences...",
      "Pre-warming 16KB slab cache...",
      "Observing kmalloc distribution shift...",
    ],
    GPU: [
      "Receiving buffers from RAM directly.",
      "Scheduling compute shaders autonomously.",
      "DMA transfer optimized via SYNAPSE.",
      "Predicting next render context...",
    ],
    SSD: [
      "Pre-loading sequential chunks.",
      "LSTM prefetch — confidence 94%.",
      "Anticipating inode lookup burst...",
      "Autonomous read-ahead triggered.",
    ],
    CACHE: [
      "Holding critical inodes dynamically.",
      "Eviction policy refined by RL agent.",
      "Hit rate climbing — model converging.",
      "Dentry cache warmed proactively.",
    ],
  };
  const STATUSES = ["Learning...", "Optimizing", "Predicting", "Stable", "Converging"];

  // ─── Smooth number animation ───
  function animateValue(element, target, suffix) {
    if (!element) return;
    const current = parseFloat(element.textContent) || 0;
    const diff = target - current;
    if (Math.abs(diff) < 0.1) {
      element.textContent = target.toFixed(suffix === "%" ? 1 : 0) + (suffix || "");
      return;
    }
    const step = diff * 0.3;
    const next = current + step;
    element.textContent = next.toFixed(suffix === "%" ? 1 : 0) + (suffix || "");
  }

  // ─── Update Components ───
  function updateComponents() {
    COMPONENTS.forEach((name) => {
      // Simulate learning: confidence slowly improves over time
      const base = { RAM: 85, GPU: 92, SSD: 78, CACHE: 99 };
      const learningBoost = Math.min(10, globalState.cycle * 0.1); // Gets better over time!
      const noise = (Math.random() - 0.5) * 4;
      const conf = Math.min(99.9, Math.max(50, base[name] + learningBoost + noise));
      globalState.confidence[name] = conf;

      // Patterns grow with each cycle
      globalState.patterns[name] += Math.floor(Math.random() * 5) + 1;
      globalState.predictions[name] += Math.floor(Math.random() * 3);

      const confEl = $(`#${name.toLowerCase()}-conf`);
      if (confEl) animateValue(confEl, conf, "%");

      const patEl = $(`#${name.toLowerCase()}-patterns`);
      if (patEl) patEl.textContent = globalState.patterns[name];

      const secondaryMap = { RAM: "ram-miss", GPU: "gpu-draw", SSD: "ssd-io", CACHE: "cache-hit" };
      const secEl = $(`#${secondaryMap[name]}`);
      if (secEl) {
        if (name === "RAM") secEl.textContent = (Math.random() * 2).toFixed(1) + " ms";
        else if (name === "GPU") secEl.textContent = "Direct P2P";
        else if (name === "SSD") secEl.textContent = (Math.random() * 3).toFixed(1) + "%";
        else secEl.textContent = (97 + Math.random() * 3).toFixed(1) + "%";
      }

      const actionEl = $(`#${name.toLowerCase()}-action`);
      if (actionEl) actionEl.textContent = AI_ACTIONS[name][Math.floor(Math.random() * AI_ACTIONS[name].length)];

      const card = $(`#node-${name.toLowerCase()}`);
      if (card) {
        const statusEl = card.querySelector(".ai-status");
        if (statusEl) {
          const st = STATUSES[Math.floor(Math.random() * STATUSES.length)];
          statusEl.textContent = st;
          statusEl.classList.toggle("active", st === "Predicting");
        }
      }
    });
  }

  // ─── CPU ───
  function updateCPU() {
    const fill = $("#cpu-fill");
    if (fill) {
      const usage = Math.random() * 1.5;
      fill.style.width = usage + "%";
      fill.style.transition = "width 0.8s ease";
    }
    const learnEl = $("#learn-cycles");
    if (learnEl) learnEl.textContent = globalState.cycle;

    // Show average prediction accuracy
    const predEl = $("#pred-accuracy");
    if (predEl) {
      const avg = Object.values(globalState.confidence).reduce((a, b) => a + b, 0) / 4;
      predEl.textContent = avg.toFixed(1) + "%";
    }
  }

  // ─── P2P Log ───
  function addP2PEntry() {
    const logEl = $("#p2p-log");
    if (!logEl) return;

    globalState.p2pCount++;

    const now = new Date();
    const ts = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;

    const isAI = Math.random() < 0.2;
    let html;

    if (isAI) {
      const comp = COMPONENTS[Math.floor(Math.random() * COMPONENTS.length)];
      const reward = (Math.random() * 1.5 - 0.3).toFixed(2);
      html = `<div class="log-entry fade-in"><span class="time">[${ts}]</span> <span class="tag hint">SYNAPSE AI</span> : Reward ${reward > 0 ? "+" : ""}${reward} to ${comp} RL Agent</div>`;
    } else {
      const msg = P2P_MESSAGES[Math.floor(Math.random() * P2P_MESSAGES.length)];
      html = `<div class="log-entry fade-in"><span class="time">[${ts}]</span> <span class="tag from">${msg.from}</span> <span class="arrow">→</span> <span class="tag to">${msg.to}</span> : ${msg.msg}</div>`;
    }

    logEl.insertAdjacentHTML("beforeend", html);
    while (logEl.children.length > 50) logEl.removeChild(logEl.firstChild);
    logEl.scrollTop = logEl.scrollHeight;
  }

  // ─── Dynamic styles ───
  const style = document.createElement("style");
  style.textContent = `
    .fade-in { animation: fadeIn 0.4s ease-in; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
    .component-card { transition: border-color 0.5s ease, box-shadow 0.5s ease; }
    .component-card.highlight-pulse { border-color: var(--accent) !important; box-shadow: 0 0 20px rgba(0, 240, 255, 0.25) !important; }
  `;
  document.head.appendChild(style);

  function pulseRandomCard() {
    const cards = $$(".component-card");
    cards.forEach((c) => c.classList.remove("highlight-pulse"));
    const target = cards[Math.floor(Math.random() * cards.length)];
    if (target) {
      target.classList.add("highlight-pulse");
      setTimeout(() => target.classList.remove("highlight-pulse"), 2000);
    }
  }

  // ─── Taskbar Updates ───
  function updateTaskbar() {
    const tbP2P = $("#tb-p2p");
    const tbLearn = $("#tb-learn");
    const tbPred = $("#tb-pred");
    if (tbP2P) tbP2P.innerHTML = `P2P: <strong>${globalState.p2pCount}</strong> msgs`;
    if (tbLearn) tbLearn.innerHTML = `Learn: <strong>Cycle ${globalState.cycle}</strong>`;
    if (tbPred) {
      const avg = Object.values(globalState.confidence).reduce((a, b) => a + b, 0) / 4;
      tbPred.innerHTML = `Pred: <strong>${avg.toFixed(1)}%</strong>`;
    }
  }

  // ─── Backend Fetch ───
  async function fetchRealData() {
    try {
      const resp = await fetch("/api/status");
      if (!resp.ok) return null;
      return await resp.json();
    } catch { return null; }
  }

  async function tick() {
    globalState.cycle++;

    const data = await fetchRealData();
    if (data && data.components) {
      for (const [name, stats] of Object.entries(data.components)) {
        const confEl = $(`#${name.toLowerCase()}-conf`);
        if (confEl && stats.accuracy !== undefined) {
          animateValue(confEl, parseFloat(stats.accuracy), "%");
        }
      }
    } else {
      updateComponents();
      updateCPU();
      addP2PEntry();
    }

    updateTaskbar();

    if (globalState.cycle % 4 === 0) pulseRandomCard();
  }

  // ─── Settings sliders ───
  $$(".setting-slider").forEach(slider => {
    const valEl = slider.parentElement.querySelector(".setting-val");
    if (valEl) {
      slider.addEventListener("input", () => {
        const label = slider.parentElement.querySelector("label")?.textContent || "";
        if (label.includes("Learning Rate")) valEl.textContent = (slider.value / 1000).toFixed(3);
        else if (label.includes("Exploration")) valEl.textContent = (slider.value / 100).toFixed(2);
        else if (label.includes("Interval")) valEl.textContent = slider.value + "s";
        else if (label.includes("Threshold")) valEl.textContent = slider.value + "%";
      });
    }
  });

  // ─── Init ───
  updateComponents();
  updateCPU();
  updateTaskbar();
  setInterval(tick, 2000);

})();

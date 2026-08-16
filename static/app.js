(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const AUTO_DIAL_STORAGE_KEY = "discador-auto-dial-session-v1";

  const state = {
    config: { stages: {}, outcomes: {} },
    summary: {},
    contacts: [],
    funnel: [],
    funnelMeta: { cities: [], priorities: [] },
    queue: [],
    history: [],
    status: null,
    statusRefreshing: false,
    view: "dashboard",
    selectedOutcome: "",
    dialerContactId: null,
    editingId: null,
    autoDial: {
      running: false,
      waitingHuman: false,
      advancing: false,
      currentId: null,
      attemptStartedAt: 0,
      attempted: new Set(),
      ringTimeoutMs: 40000,
    },
  };

  const viewLabels = {
    dashboard: "Visão geral",
    contacts: "Contatos",
    funnel: "Funil",
    history: "Histórico",
    settings: "Configuração",
  };

  const icons = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    history: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5M12 7v5l3 2"/>',
    sliders: '<line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/><circle cx="8" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="10" cy="18" r="2"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>',
    moon: '<path d="M21 12.8A8.5 8.5 0 1 1 11.2 3 6.5 6.5 0 0 0 21 12.8Z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    refresh: '<path d="M20 11a8.1 8.1 0 0 0-14.8-3L3 11"/><path d="M3 5v6h6M4 13a8.1 8.1 0 0 0 14.8 3L21 13"/><path d="M21 19v-6h-6"/>',
    layers: '<path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 17l9 5 9-5"/>',
    calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    phone: '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.12.9.33 1.78.62 2.63a2 2 0 0 1-.45 2.11L8 9.73a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.85.29 1.73.5 2.63.62A2 2 0 0 1 22 16.92Z"/>',
    "phone-off": '<path d="M10.7 5.1a2 2 0 0 0-1.6-1.38A19.8 19.8 0 0 0 6.47 3.4M2 2l20 20M6.7 10.8a16 16 0 0 0 6.5 6.5l1.27-1.27a2 2 0 0 1 2.11-.45c.85.29 1.73.5 2.63.62A2 2 0 0 1 21 18.2v1.72a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 1.12 4.18 2 2 0 0 1 3.11 2h1.7"/>',
    "phone-forwarded": '<polyline points="19 1 23 5 19 9"/><line x1="15" y1="5" x2="23" y2="5"/><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.8 19.8 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.12 4.18 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.12.9.33 1.78.62 2.63a2 2 0 0 1-.45 2.11L8 9.73a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.85.29 1.73.5 2.63.62A2 2 0 0 1 22 16.92Z"/>',
    "volume-2": '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14"/>',
    "skip-forward": '<polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19"/>',
    upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>',
    smartphone: '<rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
    "hard-drive": '<line x1="22" y1="12" x2="2" y2="12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11Z"/><line x1="6" y1="16" x2="6.01" y2="16"/><line x1="10" y1="16" x2="10.01" y2="16"/>',
    x: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z"/>',
    "trash-2": '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6"/>',
    play: '<polygon points="5 3 19 12 5 21 5 3"/>',
    pause: '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
    zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "thumbs-up": '<path d="M7 10v12H3a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h4Z"/><path d="M7 10l5-8a3 3 0 0 1 3 3v4h5a2 2 0 0 1 2 2l-1.3 8a3 3 0 0 1-3 3H7"/>',
    "thumbs-down": '<path d="M7 14V2H3a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h4Z"/><path d="m7 14 5 8a3 3 0 0 0 3-3v-4h5a2 2 0 0 0 2-2l-1.3-8a3 3 0 0 0-3-3H7"/>',
    "calendar-check": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18m5 6 2 2 4-4"/>',
    voicemail: '<circle cx="6" cy="12" r="4"/><circle cx="18" cy="12" r="4"/><path d="M6 16h12"/>',
    hash: '<path d="M4 9h16M3 15h16M10 3 8 21M16 3l-2 18"/>',
    "minus-circle": '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/>',
    "map-pin": '<path d="M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
    building: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 7h2M15 7h2M7 11h2M15 11h2M7 15h2M15 15h2M10 21v-4h4v4"/>',
    external: '<path d="M14 3h7v7M10 14 21 3M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/>',
    clock: '<circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15 14"/>',
    "chevron-right": '<polyline points="9 18 15 12 9 6"/>',
    "alert-circle": '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
    "check-circle": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
  };

  function icon(name) {
    return `<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${icons[name] || icons.info}</svg>`;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function initials(contact) {
    const value = String(contact?.name || "?").trim();
    const parts = value.split(/\s+/).filter(Boolean);
    return escapeHtml((parts[0]?.[0] || "?") + (parts.length > 1 ? parts.at(-1)[0] : ""));
  }

  function stageLabel(stage) {
    return state.config.stages?.[stage] || stage || "Novo";
  }

  function outcomeLabel(outcome) {
    return state.config.outcomes?.[outcome] || outcome || "—";
  }

  function formatDate(value, withTime = false) {
    if (!value) return "—";
    const parsed = new Date(value.includes?.("T") ? value : `${value}T12:00:00`);
    if (Number.isNaN(parsed.getTime())) return value;
    return new Intl.DateTimeFormat("pt-BR", withTime ? { dateStyle: "short", timeStyle: "short" } : { dateStyle: "short" }).format(parsed);
  }

  function formatDuration(seconds) {
    const total = Number(seconds || 0);
    if (total < 60) return `${total}s`;
    return `${Math.floor(total / 60)}m ${String(total % 60).padStart(2, "0")}s`;
  }

  function isDue(value) {
    return Boolean(value && String(value).slice(0, 10) <= new Date().toISOString().slice(0, 10));
  }

  function dateTimeLocalValue(value) {
    if (!value) return "";
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value) && !String(value).endsWith("Z")) return String(value).slice(0, 16);
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return `${value}T09:00`;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "";
    const local = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
  }

  function safeHref(value) {
    try {
      const parsed = new URL(String(value || ""));
      return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : "";
    } catch { return ""; }
  }

  function priorityClass(value) {
    return String(value || "base").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      cache: "no-store",
      headers: { Accept: "application/json", ...(options.body ? { "Content-Type": "application/json" } : {}) },
      ...options,
    });
    let data = {};
    try { data = await response.json(); } catch { data = {}; }
    if (!response.ok || data.ok === false) throw new Error(data.error || `Falha na solicitação (${response.status})`);
    return data;
  }

  function showToast(message, type = "info") {
    const stack = $("#toast-stack");
    if (!stack) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type === "error" ? "is-error" : type === "success" ? "is-success" : ""}`;
    toast.innerHTML = `${icon(type === "error" ? "alert-circle" : type === "success" ? "check-circle" : "info")}<span>${escapeHtml(message)}</span>`;
    stack.append(toast);
    window.setTimeout(() => toast.remove(), 4300);
  }

  function injectIcons() {
    $$(".icon[data-icon]").forEach((node) => { node.innerHTML = icon(node.dataset.icon); });
  }

  function updateClock() {
    const node = $("#topbar-clock");
    if (node) node.textContent = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(new Date());
  }

  function renderStageOptions() {
    const filter = $("#contact-stage-filter");
    const dialog = $("#dialog-stage");
    if (!filter || !dialog) return;
    const currentFilter = filter.value;
    filter.innerHTML = `<option value="">Todas as etapas</option>${Object.entries(state.config.stages).map(([key, label]) => `<option value="${escapeHtml(key)}">${escapeHtml(label)}</option>`).join("")}`;
    filter.value = currentFilter;
    dialog.innerHTML = Object.entries(state.config.stages).map(([key, label]) => `<option value="${escapeHtml(key)}">${escapeHtml(label)}</option>`).join("");
  }

  function showView(view) {
    if (!viewLabels[view]) return;
    state.view = view;
    $$('[data-view]').forEach((section) => section.classList.toggle("is-active", section.dataset.view === view));
    $$('[data-view-target]').forEach((button) => button.classList.toggle("is-active", button.dataset.viewTarget === view && button.classList.contains("nav-item")));
    $("#page-context").textContent = viewLabels[view];
    if (view === "contacts") loadContacts();
    if (view === "funnel") loadFunnel();
    if (view === "history") loadHistory();
    if (view === "settings") renderSettings(state.status);
  }

  function renderSummary() {
    const summary = state.summary || {};
    $("#metric-total").textContent = summary.total ?? 0;
    $("#metric-active").textContent = summary.active ?? 0;
    $("#metric-due").textContent = summary.due ?? 0;
    $("#metric-calls").textContent = summary.calls_today ?? 0;
    $("#nav-contact-count").textContent = summary.total ?? 0;
  }

  function statusText(status) {
    return { idle: "Parado", dialing: "Chamando", ringing: "Chamando", active: "Em chamada", disconnected: "Desconectada", offline: "Celular offline", unknown: "Status incerto" }[status] || "Parado";
  }

  function renderStatus(data) {
    if (!data) return;
    const phone = data.phone || {};
    const online = Boolean(phone.connected);
    const callStatus = data.call_status || "idle";
    const dotClasses = online ? "is-online" : "is-offline";
    [$("#sidebar-status-dot"), $("#header-status-dot"), $("#settings-status-dot")].forEach((dot) => {
      if (!dot) return;
      dot.className = `status-dot ${dot.classList.contains("status-dot-large") ? "status-dot-large " : ""}${dotClasses}`;
    });
    const deviceLabel = online ? "Celular conectado" : "Celular offline";
    const detail = online ? `${phone.model || "Android"}${phone.serial ? ` · ${phone.serial}` : ""}` : (phone.error || "ADB via Wi-Fi");
    $("#sidebar-device-state").textContent = online ? "Celular conectado" : "Celular offline";
    $("#sidebar-device-model").textContent = online ? (phone.model || "Android") : "ADB via Wi-Fi";
    $("#header-status-label").textContent = deviceLabel;
    $("#header-status-detail").textContent = detail;
    $("#settings-status-label").textContent = online ? `${phone.model || "Android"} conectado` : "Celular não encontrado";
    $("#settings-model").textContent = phone.model || "—";
    $("#settings-android").textContent = phone.android || "—";
    $("#settings-serial").textContent = phone.serial || "—";
    $("#settings-adb-path").textContent = phone.adb_path || "—";
    const card = $("#header-status-card");
    if (card) card.classList.toggle("is-offline", !online);
    renderDialer(data);
    renderAutoOperation();
  }

  function renderAutoOperation() {
    const auto = state.autoDial;
    persistAutoDial();
    const statusNode = $("#auto-operation-status");
    const progressNode = $("#auto-progress");
    const startButton = $("#auto-start-button");
    const pauseButton = $("#auto-pause-button");
    const panel = $("#auto-operation");
    if (!statusNode || !progressNode || !startButton || !pauseButton || !panel) return;
    let label = "Uma chamada por vez; para quando a ligação conectar.";
    if (auto.advancing) label = "Registrando a tentativa e preparando o próximo lead...";
    else if (auto.waitingHuman) label = "Ligação conectada ou operação pausada. Classifique o atendimento para continuar.";
    else if (auto.running) label = "Discando a fila; o sistema interrompe a sequência assim que conectar.";
    statusNode.textContent = label;
    progressNode.textContent = `${auto.attempted.size} ${auto.attempted.size === 1 ? "tentativa" : "tentativas"}`;
    startButton.disabled = auto.running || auto.advancing || auto.waitingHuman;
    startButton.innerHTML = `${icon("play")} ${auto.attempted.size ? "Retomar" : "Iniciar"}`;
    pauseButton.disabled = !auto.running;
    panel.classList.toggle("is-running", auto.running || auto.advancing);
    panel.classList.toggle("is-waiting", auto.waitingHuman);
  }

  function persistAutoDial() {
    try {
      sessionStorage.setItem(AUTO_DIAL_STORAGE_KEY, JSON.stringify({
        running: state.autoDial.running,
        waitingHuman: state.autoDial.waitingHuman,
        currentId: state.autoDial.currentId,
        attemptStartedAt: state.autoDial.attemptStartedAt,
        attempted: [...state.autoDial.attempted],
        savedAt: Date.now(),
      }));
    } catch { /* armazenamento indisponível não pode parar o discador */ }
  }

  function restoreAutoDial() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(AUTO_DIAL_STORAGE_KEY) || "null");
      if (!saved || Date.now() - Number(saved.savedAt || 0) > 4 * 60 * 60 * 1000) return;
      state.autoDial.running = Boolean(saved.running);
      state.autoDial.waitingHuman = Boolean(saved.waitingHuman);
      state.autoDial.currentId = Number(saved.currentId) || null;
      state.autoDial.attemptStartedAt = Number(saved.attemptStartedAt) || 0;
      state.autoDial.attempted = new Set((saved.attempted || []).map(Number).filter(Boolean));
      state.autoDial.advancing = false;
    } catch {
      sessionStorage.removeItem(AUTO_DIAL_STORAGE_KEY);
    }
  }

  function reconcileAutoDial(data) {
    const serverContact = data?.active;
    const callStatus = data?.call_status || "idle";
    if (!serverContact || !["active", "disconnected"].includes(callStatus)) return;
    if (!state.autoDial.currentId) {
      state.autoDial.currentId = Number(serverContact.id);
      state.autoDial.attempted.add(Number(serverContact.id));
      state.autoDial.running = false;
      state.autoDial.waitingHuman = true;
      persistAutoDial();
    }
  }

  function renderDialer(data) {
    const contact = data.active || data.selected;
    const callStatus = data.call_status || "idle";
    const active = Boolean(data.active);
    const contactId = contact?.id || null;
    if (state.dialerContactId !== contactId) {
      state.dialerContactId = contactId;
      state.selectedOutcome = "";
      const notes = $("#call-notes");
      const date = $("#call-return-date");
      if (notes) notes.value = "";
      if (date) date.value = "";
    }
    const contactNode = $("#dialer-contact");
    const actions = $("#dialer-actions");
    const outcomeSection = $("#outcome-section");
    const badge = $("#call-state-badge");
    badge.textContent = statusText(callStatus);
    badge.className = `call-state-badge ${["dialing", "ringing"].includes(callStatus) ? "is-ringing" : callStatus === "active" ? "is-active" : callStatus === "disconnected" ? "is-disconnected" : ""}`;
    if (!contact) {
      contactNode.innerHTML = `<div class="empty-state compact-empty"><span class="empty-icon">${icon("phone-forwarded")}</span><strong>Selecione um contato para começar</strong><span>Escolha alguém da fila ou da tela de contatos.</span><button class="button button-secondary" id="select-first-contact" data-action="select-first" type="button">Selecionar primeiro da fila</button></div>`;
      actions.hidden = true;
      outcomeSection.hidden = true;
      return;
    }
    const instagramHref = safeHref(contact.instagram);
    const facebookHref = safeHref(contact.facebook);
    const sourceHref = safeHref(contact.source_url);
    contactNode.innerHTML = `<div class="contact-focus">
      <div class="avatar">${initials(contact)}</div>
      <div class="focus-copy">
        <div class="focus-name">${escapeHtml(contact.company || contact.name)}</div>
        <div class="focus-company">${escapeHtml(contact.name)}${contact.responsible_role ? ` · ${escapeHtml(contact.responsible_role)}` : ""}</div>
        <div class="focus-meta">
          <span>${icon("phone")}${escapeHtml(contact.phone || "Sem telefone")}</span>
          ${contact.city ? `<span>${icon("map-pin")}${escapeHtml(contact.city)}</span>` : ""}
          ${contact.return_date ? `<span>${icon("calendar")}${escapeHtml(formatDate(contact.return_date, true))}</span>` : ""}
          ${contact.priority ? `<span class="priority-tag priority-${priorityClass(contact.priority)}">${escapeHtml(contact.priority)}</span>` : ""}
        </div>
        <div class="lead-detail-grid">
          ${contact.cnpj ? `<span><small>CNPJ</small><strong>${escapeHtml(contact.cnpj)}</strong></span>` : ""}
          ${contact.category ? `<span><small>Categoria</small><strong>${escapeHtml(contact.category)}</strong></span>` : ""}
          ${contact.email ? `<span><small>E-mail</small><strong>${escapeHtml(contact.email)}</strong></span>` : ""}
          ${contact.confidence ? `<span><small>Fonte</small><strong>${escapeHtml(contact.confidence)}</strong></span>` : ""}
        </div>
        ${(instagramHref || facebookHref || sourceHref) ? `<div class="lead-links">${instagramHref ? `<a href="${escapeHtml(instagramHref)}" target="_blank" rel="noreferrer">Instagram ${icon("external")}</a>` : ""}${facebookHref ? `<a href="${escapeHtml(facebookHref)}" target="_blank" rel="noreferrer">Facebook ${icon("external")}</a>` : ""}${sourceHref ? `<a href="${escapeHtml(sourceHref)}" target="_blank" rel="noreferrer">Fonte ${icon("external")}</a>` : ""}</div>` : ""}
        ${(contact.notes || contact.public_note) ? `<div class="focus-notes"><strong>Observações</strong><span>${escapeHtml(contact.notes || contact.public_note)}</span></div>` : ""}
      </div>
      <div class="focus-stage"><span class="stage-pill stage-${escapeHtml(contact.stage)}">${escapeHtml(contact.stage_label || stageLabel(contact.stage))}</span></div>
    </div>`;
    actions.hidden = false;
    outcomeSection.hidden = false;
    const canCall = !active || ["idle", "disconnected", "offline", "unknown"].includes(callStatus);
    const dialButton = $("#dial-button");
    dialButton.disabled = !canCall || !contact.phone || state.autoDial.running || state.autoDial.advancing;
    dialButton.innerHTML = `${icon("phone")} ${callStatus === "disconnected" ? "Ligar novamente" : active ? "Em andamento" : "Ligar"}`;
    $("#speaker-button").disabled = !active;
    const hangupButton = $("#hangup-button");
    hangupButton.disabled = !active;
    hangupButton.innerHTML = `${icon("phone-off")} ${["idle", "disconnected"].includes(callStatus) ? "Limpar estado" : "Desligar"}`;
    const helper = $("#call-helper");
    helper.textContent = data.speaker_message || (callStatus === "active" ? "Chamada ativa: fale pelo viva-voz do celular." : callStatus === "ringing" || callStatus === "dialing" ? "Aguardando o cliente atender..." : data.last_cause ? `Último estado: ${data.last_cause}` : "O áudio fica no alto-falante e no microfone do celular.");
    $$(".outcome-button").forEach((button) => button.classList.toggle("is-selected", button.dataset.outcome === state.selectedOutcome));
    $("#outcome-hint").textContent = state.selectedOutcome ? outcomeLabel(state.selectedOutcome) : "Escolha um resultado";
    $("#next-call-button").disabled = !state.selectedOutcome;
    $("#record-button").disabled = !state.selectedOutcome;
    const callbackRow = $(".callback-date-row");
    if (callbackRow) callbackRow.hidden = !["callback", "meeting"].includes(state.selectedOutcome);
    const nextButton = $("#next-call-button");
    if (nextButton) nextButton.innerHTML = `${icon("skip-forward")} ${state.autoDial.waitingHuman ? "Registrar e continuar operação" : "Registrar e chamar próximo"}`;
  }

  function renderQueue() {
    const node = $("#queue-list");
    if (!state.queue.length) {
      node.innerHTML = `<div class="empty-state"><span class="empty-icon">${icon("users")}</span><strong>A fila está vazia</strong><span>Adicione ou importe contatos para começar.</span></div>`;
      return;
    }
    node.innerHTML = state.queue.slice(0, 10).map((contact) => `<button class="queue-item" data-select-contact="${contact.id}" type="button"><span class="avatar">${initials(contact)}</span><span class="queue-copy"><span class="queue-name">${escapeHtml(contact.company || contact.name)}</span><span class="queue-sub">${escapeHtml(contact.name)} · ${escapeHtml(contact.phone)}</span></span><span class="queue-right">${contact.return_date && isDue(contact.return_date) ? `<span class="queue-return">retorno ${escapeHtml(formatDate(contact.return_date))}</span>` : ""}<span class="icon">${icon("chevron-right")}</span></span></button>`).join("");
  }

  function funnelStageOptions(selected) {
    return Object.entries(state.config.stages || {}).map(([key, label]) => `<option value="${escapeHtml(key)}" ${key === selected ? "selected" : ""}>${escapeHtml(label)}</option>`).join("");
  }

  function filteredFunnelContacts() {
    const search = ($("#funnel-search")?.value || "").trim().toLocaleLowerCase("pt-BR");
    const city = $("#funnel-city-filter")?.value || "";
    const priority = $("#funnel-priority-filter")?.value || "";
    return state.funnel.filter((contact) => {
      if (city && contact.city !== city) return false;
      if (priority && contact.priority !== priority) return false;
      if (!search) return true;
      const haystack = [contact.company, contact.name, contact.responsible_role, contact.phone, contact.whatsapp, contact.cnpj, contact.instagram, contact.city, contact.notes]
        .join(" ").toLocaleLowerCase("pt-BR");
      return haystack.includes(search);
    });
  }

  function renderFunnelFilters() {
    const city = $("#funnel-city-filter");
    const priority = $("#funnel-priority-filter");
    if (!city || !priority) return;
    const selectedCity = city.value;
    const selectedPriority = priority.value;
    city.innerHTML = `<option value="">Todas as cidades</option>${(state.funnelMeta.cities || []).map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("")}`;
    priority.innerHTML = `<option value="">Todas as prioridades</option>${(state.funnelMeta.priorities || []).map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("")}`;
    city.value = selectedCity;
    priority.value = selectedPriority;
  }

  function funnelCard(contact) {
    const observation = contact.notes || contact.public_note || "";
    return `<article class="kanban-card" draggable="true" data-drag-contact="${contact.id}" tabindex="0">
      <div class="kanban-card-top">
        <span class="priority-tag priority-${priorityClass(contact.priority)}">${escapeHtml(contact.priority || "SEM MARCAÇÃO")}</span>
        <span class="kanban-score" title="Pontuação">${Number(contact.score || 0)} pts</span>
      </div>
      <h3>${escapeHtml(contact.company || "Estabelecimento não informado")}</h3>
      <p class="kanban-responsible">${escapeHtml(contact.name)}${contact.responsible_role ? ` · ${escapeHtml(contact.responsible_role)}` : ""}</p>
      <div class="kanban-meta">
        ${contact.city ? `<span>${icon("map-pin")}${escapeHtml(contact.city)}</span>` : ""}
        <span>${icon("phone")}${escapeHtml(contact.phone || "Sem telefone")}</span>
        ${contact.cnpj ? `<span>${icon("building")}${escapeHtml(contact.cnpj)}</span>` : ""}
        ${contact.return_date ? `<span class="${isDue(contact.return_date) ? "is-due" : ""}">${icon("calendar")}${escapeHtml(formatDate(contact.return_date, true))}</span>` : ""}
      </div>
      ${observation ? `<p class="kanban-note" title="${escapeHtml(observation)}">${escapeHtml(observation)}</p>` : ""}
      <div class="kanban-card-actions">
        <label><span class="visually-hidden">Mover ${escapeHtml(contact.company || contact.name)} para etapa</span><select data-funnel-stage data-id="${contact.id}" aria-label="Etapa de ${escapeHtml(contact.company || contact.name)}">${funnelStageOptions(contact.stage)}</select></label>
        <button class="icon-button" data-action="select" data-id="${contact.id}" type="button" title="Selecionar no discador" aria-label="Selecionar no discador" ${contact.phone ? "" : "disabled"}>${icon("phone")}</button>
        <button class="icon-button" data-action="edit" data-id="${contact.id}" type="button" title="Ver e editar dados" aria-label="Ver e editar dados">${icon("edit")}</button>
      </div>
    </article>`;
  }

  function renderFunnel() {
    const board = $("#kanban-board");
    const strip = $("#pipeline-strip");
    if (!board || !strip) return;
    const contacts = filteredFunnelContacts();
    const counts = Object.fromEntries(Object.keys(state.config.stages || {}).map((stage) => [stage, 0]));
    contacts.forEach((contact) => { counts[contact.stage] = (counts[contact.stage] || 0) + 1; });
    strip.innerHTML = Object.entries(state.config.stages || {}).map(([stage, label]) => `<button type="button" class="pipeline-chip stage-${escapeHtml(stage)}" data-funnel-filter-stage="${escapeHtml(stage)}"><span>${escapeHtml(label)}</span><strong>${counts[stage] || 0}</strong></button>`).join("");
    board.innerHTML = Object.entries(state.config.stages || {}).map(([stage, label]) => {
      const cards = contacts.filter((contact) => contact.stage === stage);
      return `<section class="kanban-column stage-column-${escapeHtml(stage)}" data-funnel-drop="${escapeHtml(stage)}">
        <header><div><span class="column-indicator"></span><h2>${escapeHtml(label)}</h2></div><strong>${cards.length}</strong></header>
        <div class="kanban-card-list">${cards.length ? cards.map(funnelCard).join("") : `<div class="kanban-empty">Solte um lead nesta etapa</div>`}</div>
      </section>`;
    }).join("");
  }

  async function loadFunnel() {
    const board = $("#kanban-board");
    if (board && !state.funnel.length) board.innerHTML = `<div class="loading-state"><span class="spinner"></span> Carregando funil...</div>`;
    try {
      const data = await api("/api/funnel");
      state.funnel = data.contacts || [];
      state.funnelMeta = { cities: data.cities || [], priorities: data.priorities || [] };
      renderFunnelFilters();
      renderFunnel();
    } catch (error) {
      if (board) board.innerHTML = `<div class="empty-state"><span class="empty-icon">${icon("alert-circle")}</span><strong>Não foi possível carregar o funil</strong><span>${escapeHtml(error.message)}</span></div>`;
      showToast(error.message, "error");
    }
  }

  async function moveFunnelContact(contactId, targetStage) {
    if (!state.config.stages?.[targetStage]) return;
    const contact = state.funnel.find((item) => Number(item.id) === Number(contactId));
    if (!contact || contact.stage === targetStage) return;
    const previousStage = contact.stage;
    contact.stage = targetStage;
    contact.stage_label = stageLabel(targetStage);
    renderFunnel();
    try {
      const data = await api(`/api/contacts/${contact.id}`, { method: "PUT", body: JSON.stringify({ stage: targetStage }) });
      Object.assign(contact, data.contact || {});
      await refreshData(true);
      showToast(`${contact.company || contact.name} movido para ${stageLabel(targetStage)}.`, "success");
    } catch (error) {
      contact.stage = previousStage;
      contact.stage_label = stageLabel(previousStage);
      renderFunnel();
      showToast(error.message, "error");
    }
  }

  function contactActions(contact) {
    return `<div class="table-actions"><button class="icon-button" data-action="dial" data-id="${contact.id}" type="button" title="Selecionar e ligar" aria-label="Selecionar e ligar para ${escapeHtml(contact.company || contact.name)}" ${contact.phone ? "" : "disabled"}><span class="icon">${icon("phone")}</span></button><button class="icon-button" data-action="edit" data-id="${contact.id}" type="button" title="Editar contato" aria-label="Editar contato"><span class="icon">${icon("edit")}</span></button><button class="icon-button" data-action="delete" data-id="${contact.id}" type="button" title="Excluir contato" aria-label="Excluir contato"><span class="icon">${icon("trash-2")}</span></button></div>`;
  }

  function renderContacts() {
    const body = $("#contacts-body");
    const mobile = $("#contacts-mobile-list");
    if (!state.contacts.length) {
      body.innerHTML = `<tr><td colspan="6" class="empty-table">Nenhum contato encontrado.</td></tr>`;
      mobile.innerHTML = `<div class="empty-state"><span class="empty-icon">${icon("users")}</span><strong>Nenhum contato encontrado</strong><span>Adicione um registro ou ajuste a busca.</span></div>`;
      return;
    }
    body.innerHTML = state.contacts.map((contact) => `<tr><td><div class="table-contact"><span class="avatar">${initials(contact)}</span><div><strong>${escapeHtml(contact.company || "Sem restaurante")}</strong><span>${escapeHtml(contact.name)}${contact.responsible_role ? ` · ${escapeHtml(contact.responsible_role)}` : ""}</span></div></div></td><td class="table-phone">${escapeHtml(contact.phone || "Sem telefone")}</td><td><span class="stage-pill stage-${escapeHtml(contact.stage)}">${escapeHtml(contact.stage_label || stageLabel(contact.stage))}</span></td><td class="table-date ${isDue(contact.return_date) ? "is-due" : ""}">${escapeHtml(formatDate(contact.return_date))}</td><td class="table-date">${escapeHtml(formatDate(contact.last_contact_at, true))}</td><td class="align-right">${contactActions(contact)}</td></tr>`).join("");
    mobile.innerHTML = state.contacts.map((contact) => `<div class="mobile-record"><div class="mobile-record-top"><div class="mobile-record-name"><span class="avatar">${initials(contact)}</span><strong>${escapeHtml(contact.company || contact.name)}</strong></div><span class="stage-pill stage-${escapeHtml(contact.stage)}">${escapeHtml(contact.stage_label || stageLabel(contact.stage))}</span></div><div class="mobile-record-meta"><span>${escapeHtml(contact.name)}${contact.responsible_role ? ` · ${escapeHtml(contact.responsible_role)}` : ""}</span><span>${escapeHtml(contact.phone || "Sem telefone")}</span><span>${contact.return_date ? `retorno ${escapeHtml(formatDate(contact.return_date))}` : "sem retorno"}</span></div><div class="mobile-record-actions">${contactActions(contact)}</div></div>`).join("");
  }

  function renderHistory() {
    const body = $("#history-body");
    const mobile = $("#history-mobile-list");
    if (!state.history.length) {
      body.innerHTML = `<tr><td colspan="5" class="empty-table">Nenhuma ligação registrada ainda.</td></tr>`;
      mobile.innerHTML = `<div class="empty-state"><span class="empty-icon">${icon("history")}</span><strong>Sem histórico</strong><span>Os registros aparecerão aqui depois da primeira chamada.</span></div>`;
      $("#history-summary").innerHTML = "";
      return;
    }
    const counts = state.history.reduce((result, item) => { result[item.outcome] = (result[item.outcome] || 0) + 1; return result; }, {});
    $("#history-summary").innerHTML = Object.entries(counts).slice(0, 6).map(([key, count]) => `<span class="history-chip"><strong>${count}</strong>${escapeHtml(outcomeLabel(key))}</span>`).join("");
    body.innerHTML = state.history.map((item) => `<tr><td><div class="table-contact"><span class="avatar">${initials(item)}</span><div><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.company || item.phone || "")}</span></div></div></td><td class="table-date">${escapeHtml(formatDate(item.ended_at, true))}</td><td><span class="outcome-tag outcome-${escapeHtml(item.outcome)}">${escapeHtml(outcomeLabel(item.outcome))}</span></td><td class="table-date">${escapeHtml(formatDuration(item.duration_seconds))}</td><td><span class="history-note" title="${escapeHtml(item.notes || "")}">${escapeHtml(item.notes || "—")}</span></td></tr>`).join("");
    mobile.innerHTML = state.history.map((item) => `<div class="mobile-record"><div class="mobile-record-top"><div class="mobile-record-name"><span class="avatar">${initials(item)}</span><strong>${escapeHtml(item.name)}</strong></div><span class="outcome-tag outcome-${escapeHtml(item.outcome)}">${escapeHtml(outcomeLabel(item.outcome))}</span></div><div class="mobile-record-meta"><span>${escapeHtml(formatDate(item.ended_at, true))}</span><span>${escapeHtml(formatDuration(item.duration_seconds))}</span></div>${item.notes ? `<div class="history-note">${escapeHtml(item.notes)}</div>` : ""}</div>`).join("");
  }

  function renderSettings(data) {
    if (data) renderStatus(data);
  }

  async function loadConfig() {
    const data = await api("/api/config");
    state.config = data;
    renderStageOptions();
  }

  async function loadContacts() {
    const search = $("#contact-search")?.value.trim() || "";
    const stage = $("#contact-stage-filter")?.value || "";
    try {
      const data = await api(`/api/contacts?search=${encodeURIComponent(search)}&stage=${encodeURIComponent(stage)}`);
      state.contacts = data.contacts || [];
      renderContacts();
    } catch (error) { showToast(error.message, "error"); }
  }

  async function loadHistory() {
    try {
      const data = await api("/api/history");
      state.history = data.history || [];
      renderHistory();
    } catch (error) { showToast(error.message, "error"); }
  }

  async function refreshData(silent = false) {
    try {
      const [summaryData, queueData, statusData] = await Promise.all([api("/api/summary"), api("/api/queue"), api("/api/status")]);
      state.summary = summaryData.summary || {};
      state.queue = queueData.contacts || [];
      state.status = statusData;
      renderSummary();
      renderQueue();
      renderStatus(statusData);
      if (state.view === "contacts") await loadContacts();
      if (state.view === "history") await loadHistory();
    } catch (error) {
      if (!silent) showToast(error.message, "error");
    }
  }

  async function refreshStatus(showError = false) {
    if (state.statusRefreshing) return;
    state.statusRefreshing = true;
    try {
      state.status = await api("/api/status");
      renderStatus(state.status);
      if (state.view === "settings") renderSettings(state.status);
      await handleAutoDial(state.status);
    } catch (error) {
      if (showError) showToast(error.message, "error");
    } finally {
      state.statusRefreshing = false;
    }
  }

  function automaticOutcome(cause) {
    const value = String(cause || "").toUpperCase();
    if (/BUSY|USER_BUSY/.test(value)) return "busy";
    if (/INVALID|UNOBTAINABLE|NUMBER_UNREACHABLE|NO_ROUTE|NOT_FOUND/.test(value)) return "wrong_number";
    if (/NO_ANSWER|MISSED|TIMED_OUT/.test(value)) return "no_answer";
    if (/CONGESTION|NETWORK|OUT_OF_SERVICE|POWER_OFF|ERROR|FAILED/.test(value)) return "dropped";
    return "no_answer";
  }

  function clearCallForm() {
    state.selectedOutcome = "";
    const notes = $("#call-notes");
    const date = $("#call-return-date");
    if (notes) notes.value = "";
    if (date) date.value = "";
  }

  async function autoDialNext() {
    const auto = state.autoDial;
    if (!auto.running || auto.advancing) return;
    auto.advancing = true;
    renderAutoOperation();
    const selected = state.status?.selected;
    const isCallable = (contact) => contact?.phone && !["ganho", "perdido"].includes(contact.stage) && !auto.attempted.has(Number(contact.id));
    const candidate = isCallable(selected) ? selected : state.queue.find(isCallable);
    if (!candidate) {
      auto.running = false;
      auto.advancing = false;
      auto.currentId = null;
      renderAutoOperation();
      showToast("A operação chegou ao fim da fila disponível.", "success");
      return;
    }
    try {
      await api("/api/dialer/select", { method: "POST", body: JSON.stringify({ contact_id: Number(candidate.id) }) });
      auto.currentId = Number(candidate.id);
      auto.attempted.add(Number(candidate.id));
      auto.attemptStartedAt = Date.now();
      clearCallForm();
      state.status = await api("/api/dialer/start", { method: "POST", body: JSON.stringify({ contact_id: Number(candidate.id) }) });
      renderStatus(state.status);
    } catch (error) {
      auto.running = false;
      auto.currentId = null;
      showToast(`A operação foi pausada: ${error.message}`, "error");
    } finally {
      auto.advancing = false;
      renderAutoOperation();
    }
  }

  async function finishAutomaticAttempt(outcome, hangupFirst = false) {
    const auto = state.autoDial;
    if (auto.advancing) return;
    auto.advancing = true;
    renderAutoOperation();
    try {
      if (hangupFirst) await api("/api/dialer/hangup", { method: "POST", body: "{}" });
      state.status = await api("/api/dialer/record", {
        method: "POST",
        body: JSON.stringify({ outcome, notes: "", return_date: "" }),
      });
      auto.currentId = null;
      auto.attemptStartedAt = 0;
      await refreshData(true);
      auto.running = true;
      auto.waitingHuman = false;
    } catch (error) {
      auto.running = false;
      showToast(`A sequência foi pausada: ${error.message}`, "error");
    } finally {
      auto.advancing = false;
      renderAutoOperation();
    }
    if (auto.running) window.setTimeout(autoDialNext, 700);
  }

  async function handleAutoDial(data) {
    const auto = state.autoDial;
    if (!auto.running || auto.advancing || !auto.currentId) return;
    const callStatus = data?.call_status || "unknown";
    if (callStatus === "active") {
      auto.running = false;
      auto.waitingHuman = true;
      showView("dashboard");
      renderAutoOperation();
      renderDialer(data);
      $("#outcome-section")?.focus({ preventScroll: false });
      showToast("Ligação conectada. Os dados do cliente estão na tela; classifique o atendimento para continuar.", "success");
      return;
    }
    if (callStatus === "disconnected") {
      await finishAutomaticAttempt(automaticOutcome(data?.last_cause));
      return;
    }
    if (["dialing", "ringing"].includes(callStatus) && Date.now() - auto.attemptStartedAt >= auto.ringTimeoutMs) {
      await finishAutomaticAttempt("no_answer", true);
      return;
    }
    if (["offline", "unknown"].includes(callStatus)) {
      auto.running = false;
      auto.waitingHuman = true;
      renderAutoOperation();
      showToast("A operação foi pausada porque o estado do celular ficou indisponível.", "error");
    }
  }

  async function startAutoOperation() {
    const auto = state.autoDial;
    if (!state.status?.phone?.connected) {
      showToast("Conecte o celular pelo ADB antes de iniciar a operação.", "error");
      return;
    }
    if (!["idle", "disconnected"].includes(state.status?.call_status || "idle")) {
      showToast("Já existe uma chamada em andamento. Termine ou classifique essa chamada primeiro.", "error");
      return;
    }
    if (!state.queue.length) {
      showToast("Não há contatos com telefone disponíveis na fila.", "info");
      return;
    }
    if (auto.attempted.size >= state.queue.length) auto.attempted = new Set();
    auto.running = true;
    auto.waitingHuman = false;
    renderAutoOperation();
    await autoDialNext();
  }

  function pauseAutoOperation() {
    const auto = state.autoDial;
    auto.running = false;
    const inProgress = auto.currentId && ["dialing", "ringing", "active"].includes(state.status?.call_status);
    auto.waitingHuman = Boolean(inProgress);
    renderAutoOperation();
    showToast(inProgress ? "Sequência pausada. A chamada atual continua até você desligar ou classificar." : "Operação pausada.", "info");
  }

  async function selectContact(contactId, notify = true) {
    try {
      await api("/api/dialer/select", { method: "POST", body: JSON.stringify({ contact_id: Number(contactId) }) });
      state.dialerContactId = null;
      state.selectedOutcome = "";
      await refreshStatus(false);
      if (notify) showToast("Contato selecionado na central.", "success");
    } catch (error) { showToast(error.message, "error"); }
  }

  async function startCall() {
    const contactId = state.status?.selected?.id || state.status?.active?.id;
    if (!contactId) { showToast("Selecione um contato primeiro.", "error"); return; }
    try {
      state.status = await api("/api/dialer/start", { method: "POST", body: JSON.stringify({ contact_id: Number(contactId) }) });
      state.selectedOutcome = "";
      renderStatus(state.status);
      showToast("Chamada iniciada pelo celular.", "success");
    } catch (error) { showToast(error.message, "error"); await refreshStatus(); }
  }

  async function callSpeaker() {
    try {
      const data = await api("/api/dialer/speaker", { method: "POST", body: "{}" });
      showToast(data.message || "Comando enviado ao celular.", data.ok === false ? "error" : "success");
      await refreshStatus();
    } catch (error) { showToast(error.message, "error"); }
  }

  async function hangupCall() {
    try {
      if (state.autoDial.running) {
        state.autoDial.running = false;
        state.autoDial.waitingHuman = true;
      }
      state.status = await api("/api/dialer/hangup", { method: "POST", body: "{}" });
      renderStatus(state.status);
      showToast("Chamada desligada.", "success");
    } catch (error) { showToast(error.message, "error"); }
  }

  function callFormPayload() {
    return {
      outcome: state.selectedOutcome,
      notes: $("#call-notes")?.value.trim() || "",
      return_date: $("#call-return-date")?.value || "",
    };
  }

  async function recordCall(goNext) {
    if (!state.selectedOutcome) { showToast("Escolha o resultado da chamada.", "error"); return; }
    if (["callback", "meeting"].includes(state.selectedOutcome) && !$("#call-return-date")?.value) {
      showToast("Informe a data e a hora do retorno ou da reunião.", "error");
      $("#call-return-date")?.focus();
      return;
    }
    const assisted = state.autoDial.waitingHuman;
    const endpoint = assisted ? "/api/dialer/record" : (goNext ? "/api/dialer/next" : "/api/dialer/record");
    try {
      state.status = await api(endpoint, { method: "POST", body: JSON.stringify({ ...callFormPayload(), ...(!assisted && goNext ? { auto_start: true } : {}) }) });
      clearCallForm();
      if (assisted) {
        state.autoDial.waitingHuman = false;
        state.autoDial.currentId = null;
        state.autoDial.attemptStartedAt = 0;
        state.autoDial.running = Boolean(goNext);
      }
      renderStatus(state.status);
      await refreshData(true);
      showToast(assisted && goNext ? "Resultado salvo. A operação seguirá para o próximo lead." : goNext ? "Resultado salvo. Próximo contato carregado." : "Resultado salvo no histórico.", "success");
      if (assisted && goNext) window.setTimeout(autoDialNext, 500);
    } catch (error) {
      if (assisted) state.autoDial.running = false;
      showToast(error.message, "error");
      await refreshData(true);
    }
  }

  async function connectPhone() {
    const buttons = [$("#sidebar-connect"), $("#settings-connect")].filter(Boolean);
    buttons.forEach((button) => { button.disabled = true; });
    try {
      const data = await api("/api/adb/connect", { method: "POST", body: "{}" });
      showToast(data.phone?.connected ? "Celular encontrado pelo ADB." : (data.phone?.error || "Celular não encontrado."), data.phone?.connected ? "success" : "error");
      await refreshStatus(true);
    } catch (error) { showToast(error.message, "error"); }
    finally { buttons.forEach((button) => { button.disabled = false; }); }
  }

  function getContact(contactId) {
    return state.contacts.find((contact) => Number(contact.id) === Number(contactId))
      || state.funnel.find((contact) => Number(contact.id) === Number(contactId))
      || state.queue.find((contact) => Number(contact.id) === Number(contactId));
  }

  function openContactDialog(contact = null) {
    const dialog = $("#contact-dialog");
    const form = $("#contact-form");
    state.editingId = contact?.id || null;
    $("#dialog-eyebrow").textContent = contact ? "EDITAR REGISTRO" : "NOVO REGISTRO";
    $("#dialog-title").textContent = contact ? "Editar contato" : "Adicionar contato";
    const values = contact || { name: "", company: "", phone: "", stage: "novo", priority: "", return_date: "", notes: "" };
    const fields = [
      "name", "responsible_role", "company", "phone", "whatsapp", "stage", "priority", "return_date", "score", "notes",
      "city", "category", "address", "legal_company", "cnpj", "email", "website", "instagram", "facebook", "confidence", "source_url", "public_note",
    ];
    fields.forEach((field) => {
      const control = form.elements.namedItem(field);
      if (!control) return;
      if (field === "return_date") control.value = dateTimeLocalValue(values[field]);
      else if (field === "stage") control.value = values[field] || "novo";
      else control.value = values[field] ?? "";
    });
    const phoneControl = form.elements.namedItem("phone");
    if (phoneControl) phoneControl.required = !contact?.source_key;
    const disclosure = $(".form-disclosure", form);
    if (disclosure) disclosure.open = Boolean(contact && ["city", "cnpj", "instagram", "facebook", "source_url", "public_note"].some((field) => contact[field]));
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    form.elements.namedItem("name")?.focus();
  }

  async function saveContact(event) {
    event.preventDefault();
    if (event.submitter?.value === "cancel") { $("#contact-dialog").close(); return; }
    const form = $("#contact-form");
    const data = Object.fromEntries(new FormData(form).entries());
    const endpoint = state.editingId ? `/api/contacts/${state.editingId}` : "/api/contacts";
    try {
      await api(endpoint, { method: state.editingId ? "PUT" : "POST", body: JSON.stringify(data) });
      $("#contact-dialog").close();
      await refreshData(true);
      await loadContacts();
      if (state.view === "funnel") await loadFunnel();
      showToast(state.editingId ? "Contato atualizado." : "Contato adicionado à base.", "success");
    } catch (error) { showToast(error.message, "error"); }
  }

  async function deleteContact(contactId) {
    const contact = getContact(contactId);
    if (!contact || !window.confirm(`Excluir ${contact.name}? O histórico desse contato também será removido.`)) return;
    try {
      await api(`/api/contacts/${contactId}`, { method: "DELETE" });
      await refreshData(true);
      await loadContacts();
      if (state.view === "funnel") await loadFunnel();
      showToast("Contato excluído.", "success");
    } catch (error) { showToast(error.message, "error"); }
  }

  async function importCsv(file) {
    if (!file) return;
    const form = new FormData();
    form.append("file", file, file.name);
    try {
      const response = await fetch("/api/import", { method: "POST", body: form, cache: "no-store" });
      const data = await response.json();
      if (!response.ok || data.ok === false) throw new Error(data.error || "Falha ao importar CSV.");
      await refreshData(true);
      await loadContacts();
      showToast(`${data.created || 0} contato(s) importado(s).${data.errors?.length ? ` ${data.errors.length} linha(s) ignorada(s).` : ""}`, data.errors?.length ? "info" : "success");
    } catch (error) { showToast(error.message, "error"); }
  }

  function setTheme(dark) {
    document.body.classList.toggle("theme-dark", dark);
    const toggle = $("#theme-toggle");
    if (toggle) { toggle.innerHTML = `<span class="icon" data-icon="${dark ? "sun" : "moon"}" aria-hidden="true"></span>`; injectIcons(); }
    localStorage.setItem("discador-theme", dark ? "dark" : "light");
  }

  function bindEvents() {
    document.addEventListener("click", async (event) => {
      const viewTarget = event.target.closest("[data-view-target]");
      if (viewTarget) { showView(viewTarget.dataset.viewTarget); return; }
      const stageJump = event.target.closest("[data-funnel-filter-stage]");
      if (stageJump) {
        const column = $(`[data-funnel-drop="${stageJump.dataset.funnelFilterStage}"]`);
        column?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest", inline: "start" });
        return;
      }
      const queueTarget = event.target.closest("[data-select-contact]");
      if (queueTarget) { await selectContact(queueTarget.dataset.selectContact); return; }
      const action = event.target.closest("[data-action]");
      if (action) {
        const contactId = action.dataset.id;
        if (action.dataset.action === "select-first") {
          const contact = state.queue[0];
          if (contact) await selectContact(contact.id);
          else showToast("A fila está vazia. Adicione um contato primeiro.", "info");
          return;
        }
        if (action.dataset.action === "edit") { openContactDialog(getContact(contactId)); return; }
        if (action.dataset.action === "delete") { await deleteContact(contactId); return; }
        if (action.dataset.action === "select") { await selectContact(contactId, false); showView("dashboard"); return; }
        if (action.dataset.action === "dial") { await selectContact(contactId, false); await startCall(); return; }
      }
      const outcome = event.target.closest("[data-outcome]");
      if (outcome) {
        state.selectedOutcome = outcome.dataset.outcome;
        renderDialer(state.status);
        return;
      }
    });
    $("#theme-toggle").addEventListener("click", () => setTheme(!document.body.classList.contains("theme-dark")));
    $("#topbar-new-contact").addEventListener("click", () => openContactDialog());
    $("#contacts-new").addEventListener("click", () => openContactDialog());
    $("#contact-form").addEventListener("submit", saveContact);
    $("#dial-button").addEventListener("click", startCall);
    $("#auto-start-button").addEventListener("click", startAutoOperation);
    $("#auto-pause-button").addEventListener("click", pauseAutoOperation);
    $("#speaker-button").addEventListener("click", callSpeaker);
    $("#hangup-button").addEventListener("click", hangupCall);
    $("#next-call-button").addEventListener("click", () => recordCall(true));
    $("#record-button").addEventListener("click", () => recordCall(false));
    $("#queue-refresh").addEventListener("click", () => refreshData(false));
    $("#header-refresh").addEventListener("click", () => refreshData(false));
    $("#contacts-refresh").addEventListener("click", () => loadContacts());
    $("#funnel-refresh").addEventListener("click", () => loadFunnel());
    $("#history-refresh").addEventListener("click", () => loadHistory());
    $("#sidebar-connect").addEventListener("click", connectPhone);
    $("#settings-connect").addEventListener("click", connectPhone);
    $("#csv-input").addEventListener("change", (event) => { importCsv(event.target.files?.[0]); event.target.value = ""; });
    let searchTimer;
    $("#contact-search").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadContacts, 250); });
    $("#contact-stage-filter").addEventListener("change", loadContacts);
    let funnelSearchTimer;
    $("#funnel-search").addEventListener("input", () => { clearTimeout(funnelSearchTimer); funnelSearchTimer = setTimeout(renderFunnel, 180); });
    $("#funnel-city-filter").addEventListener("change", renderFunnel);
    $("#funnel-priority-filter").addEventListener("change", renderFunnel);
    document.addEventListener("change", (event) => {
      const target = event.target.closest("[data-funnel-stage]");
      if (target) moveFunnelContact(target.dataset.id, target.value);
    });
    let draggedContactId = null;
    document.addEventListener("dragstart", (event) => {
      const card = event.target.closest("[data-drag-contact]");
      if (!card) return;
      draggedContactId = Number(card.dataset.dragContact);
      card.classList.add("is-dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", String(draggedContactId));
    });
    document.addEventListener("dragend", (event) => {
      event.target.closest("[data-drag-contact]")?.classList.remove("is-dragging");
      $$('[data-funnel-drop]').forEach((column) => column.classList.remove("is-drop-target"));
      draggedContactId = null;
    });
    document.addEventListener("dragover", (event) => {
      const column = event.target.closest("[data-funnel-drop]");
      if (!column || !draggedContactId) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = "move";
      $$('[data-funnel-drop]').forEach((item) => item.classList.toggle("is-drop-target", item === column));
    });
    document.addEventListener("drop", (event) => {
      const column = event.target.closest("[data-funnel-drop]");
      if (!column) return;
      event.preventDefault();
      const contactId = draggedContactId || Number(event.dataTransfer.getData("text/plain"));
      $$('[data-funnel-drop]').forEach((item) => item.classList.remove("is-drop-target"));
      draggedContactId = null;
      if (contactId) moveFunnelContact(contactId, column.dataset.funnelDrop);
    });
  }

  async function init() {
    const savedTheme = localStorage.getItem("discador-theme");
    setTheme(savedTheme === "dark");
    updateClock();
    window.setInterval(updateClock, 30000);
    injectIcons();
    bindEvents();
    try { await loadConfig(); } catch (error) { showToast(error.message, "error"); }
    await refreshData(true);
    renderAutoOperation();
    window.setInterval(() => refreshStatus(false), 1800);
  }

  document.addEventListener("DOMContentLoaded", init);
})();

const DB_NAME = "opspm-tracker";
const DB_VERSION = 1;
const STORE_NAME = "jobState";

const ui = {
  jobs: [],
  meta: null,
  records: new Map(),
  selectedId: null,
  query: "",
  family: "All",
  type: "All",
  sponsorship: "eligible",
  remoteOnly: false,
  savedOnly: false,
  sheetOpen: false,
  loading: true,
  error: null,
};

const sponsorMeta = {
  "source-signal": { label: "Source sponsor signal", short: "Source signal", icon: "●" },
  history: { label: "H-1B history", short: "H-1B history", icon: "✓" },
  "not-stated": { label: "No refusal stated", short: "Not refused", icon: "○" },
  offers: { label: "Role says sponsorship offered", short: "Offers", icon: "+" },
  no: { label: "No sponsorship", short: "No", icon: "×" },
  "citizens-only": { label: "Citizenship required", short: "Citizens only", icon: "⚑" },
};

const app = document.querySelector("#app");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function safeUrl(value) {
  try {
    const url = new URL(String(value));
    return ["http:", "https:"].includes(url.protocol) ? escapeHtml(url.href) : "#";
  } catch {
    return "#";
  }
}

function normalizeJob(job) {
  const safeSponsor = Object.hasOwn(sponsorMeta, job.sponsorship) ? job.sponsorship : "not-stated";
  const textKeys = ["company", "role", "location", "source_name", "source_section", "role_family", "job_type", "posted", "posted_bucket", "sponsorship_scope", "sponsorship_evidence", "h1b_window", "verified_at"];
  const normalized = { ...job, sponsorship: safeSponsor };
  textKeys.forEach((key) => { normalized[key] = escapeHtml(job[key]); });
  normalized.id = String(job.id ?? "").replace(/[^a-zA-Z0-9_-]/g, "");
  normalized.apply_url = safeUrl(job.apply_url);
  normalized.source_url = safeUrl(job.source_url);
  normalized.h1b_approvals = Number.isFinite(Number(job.h1b_approvals)) ? Number(job.h1b_approvals) : 0;
  return normalized;
}

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) db.createObjectStore(STORE_NAME, { keyPath: "jobId" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function loadRecords() {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const request = db.transaction(STORE_NAME, "readonly").objectStore(STORE_NAME).getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function putRecord(record) {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const request = db.transaction(STORE_NAME, "readwrite").objectStore(STORE_NAME).put(record);
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);
  });
}

function recordFor(jobId) {
  return ui.records.get(jobId) || { jobId, saved: false, status: "Saved", notes: "", updatedAt: null };
}

function readHash() {
  const params = new URLSearchParams(location.hash.replace(/^#/, ""));
  ui.query = params.get("q") || "";
  ui.family = params.get("family") || "All";
  ui.type = params.get("type") || "All";
  ui.sponsorship = params.get("sponsor") || "eligible";
  ui.remoteOnly = params.get("remote") === "1";
}

function writeHash() {
  const params = new URLSearchParams();
  if (ui.query) params.set("q", ui.query);
  if (ui.family !== "All") params.set("family", ui.family);
  if (ui.type !== "All") params.set("type", ui.type);
  if (ui.sponsorship !== "eligible") params.set("sponsor", ui.sponsorship);
  if (ui.remoteOnly) params.set("remote", "1");
  history.replaceState(null, "", params.size ? `#${params}` : location.pathname);
}

function filteredJobs() {
  return ui.jobs.filter((job) => {
    const haystack = `${job.company} ${job.role} ${job.location} ${job.role_family}`.toLowerCase();
    const record = recordFor(job.id);
    return haystack.includes(ui.query.toLowerCase()) &&
      (ui.family === "All" || job.role_family === ui.family) &&
      (ui.type === "All" || job.job_type === ui.type) &&
      (ui.sponsorship === "all" || (ui.sponsorship === "eligible" && !["no", "citizens-only"].includes(job.sponsorship)) || job.sponsorship === ui.sponsorship) &&
      (!ui.remoteOnly || /remote/i.test(job.location)) &&
      (!ui.savedOnly || record.saved);
  }).sort((a, b) => {
    const sponsorOrder = { offers: 0, "source-signal": 1, history: 2, "not-stated": 3, no: 4, "citizens-only": 5 };
    return sponsorOrder[a.sponsorship] - sponsorOrder[b.sponsorship] || a.company.localeCompare(b.company);
  });
}

function sponsorBadge(job, compact = false) {
  const meta = sponsorMeta[job.sponsorship] || sponsorMeta["not-stated"];
  return `<span class="sponsor-badge sponsor-${job.sponsorship}"><i>${meta.icon}</i>${compact ? meta.short : meta.label}</span>`;
}

function formatGeneratedAt(value) {
  if (!value) return "Update unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Update unavailable";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(date);
}

function renderFilters(mobile = false) {
  const families = ["All", "Product", "Product Ops", "Growth Ops", "Business Ops", "Strategy & Ops", "Program Management"];
  const types = ["All", "New Grad", "Internship", "Entry Level"];
  return `<div class="filters ${mobile ? "mobile-filters" : ""}">
    <div class="filter-block"><p>Role family</p><div class="chip-row">${families.map((family) => `<button data-family="${family}" class="${ui.family === family ? "active" : ""}">${family}</button>`).join("")}</div></div>
    <div class="filter-block split"><div><p>Level</p><div class="chip-row">${types.map((type) => `<button data-type="${type}" class="${ui.type === type ? "active" : ""}">${type}</button>`).join("")}</div></div><div><p>Sponsorship evidence</p><div class="chip-row"><button data-sponsor="eligible" class="${ui.sponsorship === "eligible" ? "active" : ""}">No explicit refusal</button><button data-sponsor="all" class="${ui.sponsorship === "all" ? "active" : ""}">All</button>${["source-signal", "history", "not-stated", "no"].map((key) => `<button data-sponsor="${key}" class="${ui.sponsorship === key ? "active" : ""}">${sponsorMeta[key].icon} ${sponsorMeta[key].short}</button>`).join("")}</div></div></div>
    <div class="filter-toggles"><label><input type="checkbox" data-remote ${ui.remoteOnly ? "checked" : ""}> Remote only</label><label><input type="checkbox" data-saved-only ${ui.savedOnly ? "checked" : ""}> Saved only</label></div>
  </div>`;
}

function jobRow(job) {
  const record = recordFor(job.id);
  return `<article class="job-row" data-job="${job.id}" tabindex="0">
    <div class="company-mark">${job.company.slice(0, 2).toUpperCase()}</div>
    <div class="job-copy"><small>${job.company} · ${job.posted}</small><h3>${job.role}</h3><p>${job.location} · ${job.job_type}</p></div>
    <span class="family-pill">${job.role_family}</span>
    ${sponsorBadge(job, true)}
    ${record.saved ? `<span class="status-pill">${record.status}</span>` : ""}
    <button class="quick-save ${record.saved ? "saved" : ""}" data-save="${job.id}" aria-label="${record.saved ? "Remove saved role" : "Save role"}">${record.saved ? "★" : "☆"}</button>
  </article>`;
}

function detailPanel(job) {
  if (!job) return "";
  const record = recordFor(job.id);
  return `<div class="drawer-backdrop" data-close></div><aside class="detail-drawer" role="dialog" aria-modal="true" aria-labelledby="drawer-title">
    <button class="drawer-close" data-close aria-label="Close details">×</button>
    <div class="detail-company"><div class="company-mark large">${job.company.slice(0, 2).toUpperCase()}</div><div><small>${job.company}</small><h2 id="drawer-title">${job.role}</h2></div></div>
    <div class="detail-tags"><span>${job.job_type}</span><span>${job.role_family}</span><span>${job.location}</span></div>
    <section class="evidence-card sponsor-${job.sponsorship}"><p>SPONSORSHIP EVIDENCE</p>${sponsorBadge(job)}<blockquote>${job.sponsorship_evidence}</blockquote><dl><div><dt>Evidence scope</dt><dd>${job.sponsorship_scope}</dd></div>${job.h1b_approvals ? `<div><dt>Historical approvals</dt><dd>${job.h1b_approvals.toLocaleString()} · ${job.h1b_window}</dd></div>` : ""}<div><dt>Source</dt><dd><a href="${job.source_url}" target="_blank" rel="noopener">${job.source_name} ↗</a></dd></div><div><dt>Feed checked</dt><dd>${formatGeneratedAt(job.verified_at)}</dd></div></dl><b class="evidence-warning">Past sponsorship is not a promise. Always verify the employer's own posting.</b></section>
    <section class="tracking-card"><p>YOUR TRACKER</p><label>Status<select data-status="${job.id}">${["Saved", "Reviewing", "Ready to apply", "Applying", "Submitted", "Interview", "Rejected", "Offer", "Skipped"].map((value) => `<option ${record.status === value ? "selected" : ""}>${value}</option>`).join("")}</select></label><label>Notes<textarea data-notes="${job.id}" placeholder="Add requirements, recruiter notes, or a follow-up date…">${escapeHtml(record.notes || "")}</textarea></label><small>Saved only in this browser. It is not published with the website.</small></section>
    <div class="detail-actions"><button class="save-action ${record.saved ? "saved" : ""}" data-save="${job.id}">${record.saved ? "★ Saved to tracker" : "☆ Save to tracker"}</button><a class="apply-action" href="${job.apply_url}" target="_blank" rel="noopener">View original role ↗</a></div>
  </aside>`;
}

function render() {
  if (ui.loading) return;
  if (ui.error) {
    app.innerHTML = `<main class="error-state"><p class="eyebrow">DATA UNAVAILABLE</p><h1>The opportunity feed could not load.</h1><p>${escapeHtml(ui.error)}</p><button data-retry>Try again</button><a href="./design/">View design archive</a></main>`;
    bind();
    return;
  }
  const results = filteredJobs();
  const groups = ["Fresh now", "Open roles", "Date unknown"];
  const savedCount = [...ui.records.values()].filter((record) => record.saved).length;
  const selected = ui.jobs.find((job) => job.id === ui.selectedId);
  app.innerHTML = `<div class="site-shell">
    <header class="topbar"><a class="brand" href="./"><span>O/P</span><strong>OpsPM</strong></a><div class="top-title"><b>Opportunity Radar</b><span>Early-career product + operations</span></div><div class="top-actions"><span class="refresh-status"><i></i>Updated ${formatGeneratedAt(ui.meta.generated_at)}</span><button class="saved-counter" data-toggle-saved>★ ${savedCount}</button></div></header>
    <main class="page-main">
      <section class="hero"><p class="eyebrow">2027 OPS + PRODUCT ROLES</p><h1>Know what is open.<br>Know what needs proof.</h1><p>A focused opportunity radar with transparent sponsorship evidence—not guesses.</p></section>
      <section class="filter-bar"><label class="search-control"><span>⌕</span><input type="search" value="${ui.query}" placeholder="Search roles, companies, or locations" aria-label="Search roles"></label><button class="filter-button" data-sheet>☷ Filters <b>${[ui.family !== "All", ui.type !== "All", ui.sponsorship !== "eligible", ui.remoteOnly, ui.savedOnly].filter(Boolean).length || ""}</b></button><div class="desktop-filter-summary"><button data-family="All" class="${ui.family === "All" ? "active" : ""}">All roles</button>${["Product", "Product Ops", "Growth Ops", "Business Ops", "Strategy & Ops"].map((family) => `<button data-family="${family}" class="${ui.family === family ? "active" : ""}">${family}</button>`).join("")}</div></section>
      <div class="evidence-rail"><button data-sponsor="eligible" class="${ui.sponsorship === "eligible" ? "active" : ""}">No explicit refusal</button><button data-sponsor="history" class="${ui.sponsorship === "history" ? "active" : ""}">✓ H-1B history</button><button data-sponsor="source-signal" class="${ui.sponsorship === "source-signal" ? "active" : ""}">● Source signal</button><button data-sponsor="not-stated" class="${ui.sponsorship === "not-stated" ? "active" : ""}">○ Not stated</button><span>${results.length} of ${ui.jobs.length} roles</span><a href="./design/">Design archive ↗</a></div>
      <section class="timeline">${groups.map((group) => {
        const groupJobs = results.filter((job) => job.posted_bucket === group);
        if (!groupJobs.length) return "";
        return `<div class="timeline-group"><header><span>${group === "Fresh now" ? "NOW" : "INDEX"}</span><h2>${group}</h2><b>${groupJobs.length} roles</b></header><div class="job-list">${groupJobs.map(jobRow).join("")}</div></div>`;
      }).join("") || `<div class="empty-state"><span>⌕</span><h2>No matching roles</h2><p>Try removing one filter or searching a broader title.</p><button data-clear>Clear filters</button></div>`}</section>
    </main>
    <div class="mobile-sheet ${ui.sheetOpen ? "open" : ""}"><div class="sheet-backdrop" data-sheet></div><section><button class="sheet-close" data-sheet>×</button><p class="eyebrow">FILTER YOUR RADAR</p><h2>What belongs in your feed?</h2>${renderFilters(true)}<button class="sheet-apply" data-sheet>Show ${results.length} roles</button></section></div>
    ${detailPanel(selected)}
  </div>`;
  bind();
}

function preserveSearchFocus() {
  requestAnimationFrame(() => {
    const input = document.querySelector("input[type='search']");
    if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }
  });
}

async function toggleSaved(jobId) {
  const current = recordFor(jobId);
  const next = { ...current, saved: !current.saved, updatedAt: new Date().toISOString() };
  ui.records.set(jobId, next);
  await putRecord(next);
  render();
}

function bind() {
  document.querySelector("[data-retry]")?.addEventListener("click", boot);
  document.querySelectorAll("[data-family]").forEach((button) => button.addEventListener("click", () => { ui.family = button.dataset.family; writeHash(); render(); }));
  document.querySelectorAll("[data-type]").forEach((button) => button.addEventListener("click", () => { ui.type = button.dataset.type; writeHash(); render(); }));
  document.querySelectorAll("[data-sponsor]").forEach((button) => button.addEventListener("click", () => { ui.sponsorship = button.dataset.sponsor; writeHash(); render(); }));
  document.querySelector("input[type='search']")?.addEventListener("input", (event) => { ui.query = event.target.value; writeHash(); render(); preserveSearchFocus(); });
  document.querySelectorAll("[data-remote]").forEach((input) => input.addEventListener("change", () => { ui.remoteOnly = input.checked; writeHash(); render(); }));
  document.querySelectorAll("[data-saved-only]").forEach((input) => input.addEventListener("change", () => { ui.savedOnly = input.checked; render(); }));
  document.querySelectorAll("[data-sheet]").forEach((button) => button.addEventListener("click", () => { ui.sheetOpen = !ui.sheetOpen; render(); }));
  document.querySelector("[data-toggle-saved]")?.addEventListener("click", () => { ui.savedOnly = !ui.savedOnly; render(); });
  document.querySelector("[data-clear]")?.addEventListener("click", () => { Object.assign(ui, { query: "", family: "All", type: "All", sponsorship: "eligible", remoteOnly: false, savedOnly: false }); writeHash(); render(); });
  document.querySelectorAll("[data-job]").forEach((row) => {
    const open = (event) => { if (event.target.closest("[data-save]")) return; ui.selectedId = row.dataset.job; render(); };
    row.addEventListener("click", open);
    row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") open(event); });
  });
  document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => { ui.selectedId = null; render(); }));
  document.querySelectorAll("[data-save]").forEach((button) => button.addEventListener("click", (event) => { event.stopPropagation(); toggleSaved(button.dataset.save); }));
  document.querySelector("[data-status]")?.addEventListener("change", async (event) => {
    const jobId = event.target.dataset.status; const record = { ...recordFor(jobId), saved: true, status: event.target.value, updatedAt: new Date().toISOString() };
    ui.records.set(jobId, record); await putRecord(record); render();
  });
  document.querySelector("[data-notes]")?.addEventListener("change", async (event) => {
    const jobId = event.target.dataset.notes; const record = { ...recordFor(jobId), saved: true, notes: event.target.value, updatedAt: new Date().toISOString() };
    ui.records.set(jobId, record); await putRecord(record); render();
  });
  document.removeEventListener("keydown", handleEscape);
  document.addEventListener("keydown", handleEscape);
}

function handleEscape(event) {
  if (event.key === "Escape" && (ui.selectedId || ui.sheetOpen)) { ui.selectedId = null; ui.sheetOpen = false; render(); }
}

async function boot() {
  ui.loading = true; ui.error = null;
  try {
    const [response, records] = await Promise.all([fetch("./data/jobs.json", { cache: "no-store" }), loadRecords()]);
    if (!response.ok) throw new Error(`Feed request failed (${response.status})`);
    const payload = await response.json();
    if (!Array.isArray(payload.jobs) || !payload.jobs.length) throw new Error("The feed is empty or invalid.");
    ui.jobs = payload.jobs.map(normalizeJob); ui.meta = payload; ui.records = new Map(records.map((record) => [record.jobId, record]));
  } catch (error) {
    ui.error = error.message || "Unknown loading error";
  } finally {
    ui.loading = false; render();
  }
}

readHash();
boot();

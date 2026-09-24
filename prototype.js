const jobs = [
  { id: 1, company: "Northstar", role: "Associate Product Manager — 2027", family: "Product", type: "New Grad", location: "San Francisco, CA", mode: "Hybrid", sponsor: "likely", evidence: "Company-level sponsor signal; role wording not yet verified.", date: "Today", window: "Open now", urgency: "72h", source: "2027 New Grad Index" },
  { id: 2, company: "Juniper Labs", role: "Product Operations Analyst", family: "Product Ops", type: "Entry Level", location: "New York, NY", mode: "On-site", sponsor: "verify", evidence: "No sponsorship language in the source listing. Check the employer page.", date: "Today", window: "Open now", urgency: "new", source: "Summer Role Index" },
  { id: 3, company: "Paperplane", role: "Growth Operations Associate", family: "Growth Ops", type: "New Grad", location: "Remote — US", mode: "Remote", sponsor: "unknown", evidence: "The public source has no visa field for this role.", date: "1d ago", window: "Open now", urgency: "72h", source: "Summer Role Index" },
  { id: 4, company: "Orbit", role: "Strategy & Operations Analyst", family: "Strategy & Ops", type: "Entry Level", location: "Chicago, IL", mode: "Hybrid", sponsor: "no", evidence: "Role states: candidates must not require current or future sponsorship.", date: "2d ago", window: "Open now", urgency: "skip", source: "Employer page" },
  { id: 5, company: "Luma", role: "Product Analyst, Early Career", family: "Product", type: "New Grad", location: "Seattle, WA", mode: "Hybrid", sponsor: "likely", evidence: "Role-level posting lists employment visa support as available case by case.", date: "3d ago", window: "Open now", urgency: "week", source: "Employer page" },
  { id: 6, company: "Mosaic", role: "Business Operations Coordinator", family: "Business Ops", type: "Entry Level", location: "Los Angeles, CA", mode: "On-site", sponsor: "verify", evidence: "Company has historical sponsorship records; this role is silent.", date: "4d ago", window: "September", urgency: "week", source: "2027 New Grad Index" },
  { id: 7, company: "Tandem", role: "APM Rotational Program", family: "Product", type: "New Grad", location: "Austin, TX", mode: "Hybrid", sponsor: "unknown", evidence: "Recruiting window is predicted; no live role page yet.", date: "Predicted", window: "September", urgency: "watch", source: "Timeline reference" },
  { id: 8, company: "Fieldnote", role: "Program Operations Associate", family: "Business Ops", type: "New Grad", location: "Boston, MA", mode: "Hybrid", sponsor: "likely", evidence: "Company-level sponsor signal only. Verify when the role opens.", date: "Predicted", window: "October", urgency: "watch", source: "Timeline reference" },
  { id: 9, company: "Canvas", role: "Product Management Intern", family: "Product", type: "Internship", location: "San Jose, CA", mode: "On-site", sponsor: "no", evidence: "The job-specific eligibility section explicitly excludes sponsorship.", date: "5d ago", window: "Open now", urgency: "skip", source: "Employer page" },
];

const sponsorMeta = {
  likely: { label: "Likely sponsor", short: "Likely", icon: "●" },
  verify: { label: "Needs verification", short: "Verify", icon: "◐" },
  unknown: { label: "Unknown", short: "Unknown", icon: "○" },
  no: { label: "No sponsorship", short: "No", icon: "×" },
};

const state = { query: "", family: "All", sponsor: "all", saved: new Set(), selected: null, filterOpen: false };
const design = document.body.dataset.design;
const app = document.querySelector("#app");

function filteredJobs() {
  return jobs.filter((job) => {
    const haystack = `${job.company} ${job.role} ${job.location} ${job.family}`.toLowerCase();
    return haystack.includes(state.query.toLowerCase()) &&
      (state.family === "All" || job.family === state.family) &&
      (state.sponsor === "all" || job.sponsor === state.sponsor);
  });
}

function sponsorBadge(job, compact = false) {
  const meta = sponsorMeta[job.sponsor];
  return `<span class="sponsor-badge sponsor-${job.sponsor}"><i>${meta.icon}</i>${compact ? meta.short : meta.label}</span>`;
}

function saveButton(job) {
  const saved = state.saved.has(job.id);
  return `<button class="save-button${saved ? " saved" : ""}" data-save="${job.id}" aria-label="${saved ? "Remove from saved" : "Save role"}">${saved ? "★ Saved" : "☆ Save"}</button>`;
}

function commonTop(name, subtitle, accent) {
  return `<header class="topbar ${accent}">
    <a class="brand" href="../../"><span>O/P</span><strong>OpsPM</strong></a>
    <div class="top-title"><b>${name}</b><span>${subtitle}</span></div>
    <div class="top-actions"><span class="example-label">EXAMPLE DATA</span><button class="saved-counter">★ ${state.saved.size}</button></div>
  </header>`;
}

function searchControl(placeholder = "Search roles or companies") {
  return `<label class="search-control"><span>⌕</span><input type="search" value="${state.query}" placeholder="${placeholder}" aria-label="Search roles"></label>`;
}

function filterChips() {
  const families = ["All", "Product", "Product Ops", "Growth Ops", "Business Ops", "Strategy & Ops"];
  return `<div class="filter-chips" aria-label="Role family filters">${families.map((family) => `<button data-family="${family}" class="${state.family === family ? "active" : ""}">${family}</button>`).join("")}</div>`;
}

function sponsorFilters() {
  return `<div class="sponsor-filters">
    <button data-sponsor="all" class="${state.sponsor === "all" ? "active" : ""}">All evidence</button>
    ${Object.entries(sponsorMeta).map(([key, meta]) => `<button data-sponsor="${key}" class="${state.sponsor === key ? "active" : ""}">${meta.icon} ${meta.short}</button>`).join("")}
  </div>`;
}

function details(job, layout = "drawer") {
  if (!job) return `<div class="empty-state"><strong>No role selected</strong><p>Change your filters to see more example opportunities.</p></div>`;
  return `<aside class="job-detail ${layout}">
    <div class="detail-company"><span>${job.company.slice(0, 2).toUpperCase()}</span><div><small>${job.company}</small><h2>${job.role}</h2></div></div>
    <div class="detail-tags"><span>${job.type}</span><span>${job.mode}</span><span>${job.location}</span></div>
    <section class="evidence-card sponsor-${job.sponsor}"><p>SPONSORSHIP EVIDENCE</p>${sponsorBadge(job)}<blockquote>${job.evidence}</blockquote><small>Source: ${job.source} · Checked for prototype</small></section>
    <section class="detail-copy"><p>WHY IT MATCHES</p><strong>Early-career ${job.family} role with transferable analytics, research, and cross-functional operations work.</strong></section>
    <div class="detail-actions">${saveButton(job)}<button class="primary-button">View original role ↗</button></div>
    <p class="prototype-note">Prototype only — links and listings are examples.</p>
  </aside>`;
}

function renderA() {
  const results = filteredJobs();
  const groups = ["Open now", "September", "October"];
  app.innerHTML = `<div class="design-a">
    ${commonTop("Radar Timeline", "Timing-first opportunity discovery", "mint")}
    <main>
      <section class="a-hero"><p class="eyebrow">2027 OPS + PRODUCT ROLES</p><h1>Know what is open.<br>Know what needs proof.</h1><p>A focused timeline for early-career product and operations opportunities.</p></section>
      <section class="a-filterbar">${searchControl()}${filterChips()}<button class="evidence-toggle ${state.sponsor !== "all" ? "active" : ""}" data-cycle-sponsor>Visa evidence: ${state.sponsor === "all" ? "All" : sponsorMeta[state.sponsor].short}</button></section>
      <div class="a-summary"><strong>${results.length}</strong> matching roles <span>·</span> <b>${results.filter((j) => j.window === "Open now").length} open now</b><span>·</span><b>${results.filter((j) => j.sponsor === "likely").length} sponsor signals</b></div>
      <section class="timeline-list">${groups.map((group) => {
        const groupJobs = results.filter((job) => job.window === group);
        if (!groupJobs.length) return "";
        return `<div class="timeline-group"><div class="timeline-heading"><span>${group === "Open now" ? "NOW" : "2026"}</span><h2>${group}</h2><b>${groupJobs.length} roles</b></div><div class="timeline-roles">${groupJobs.map((job) => `<article class="timeline-role ${state.selected === job.id ? "selected" : ""}" data-select="${job.id}"><div class="role-logo">${job.company.slice(0, 2)}</div><div class="role-main"><small>${job.company} · ${job.date}</small><h3>${job.role}</h3><p>${job.location} · ${job.mode}</p></div><span class="family-pill">${job.family}</span>${sponsorBadge(job, true)}<button class="row-arrow" aria-label="View role">↗</button></article>`).join("")}</div></div>`;
      }).join("") || `<div class="empty-state"><strong>No matches yet.</strong><p>Try a broader role family or visa evidence filter.</p></div>`}</section>
    </main>
    <div class="a-detail-overlay ${state.selected ? "open" : ""}">${details(jobs.find((job) => job.id === state.selected))}</div>
  </div>`;
}

function renderB() {
  const results = filteredJobs();
  const selected = results.find((job) => job.id === state.selected) || results[0];
  app.innerHTML = `<div class="design-b">
    ${commonTop("Evidence Desk", "Research-grade job screening", "blue")}
    <div class="desk-layout">
      <aside class="desk-sidebar"><p class="eyebrow">FILTER STACK</p>${searchControl("Search the index")}
        <section><h3>Role family</h3>${filterChips()}</section>
        <section><h3>Sponsorship</h3>${sponsorFilters()}</section>
        <section class="source-box"><h3>Source health</h3><p><i class="live-dot"></i> 2 feeds refreshed</p><p>1 timeline reference</p><small>Example status · no live fetch</small></section>
      </aside>
      <main class="desk-main"><div class="desk-heading"><div><p class="eyebrow">OPPORTUNITY INDEX</p><h1>${results.length} roles require your attention</h1></div><button class="secondary-button">Export view</button></div>
        <div class="table-shell"><table><thead><tr><th>Company / role</th><th>Track</th><th>Location</th><th>Posted</th><th>Sponsorship evidence</th><th></th></tr></thead><tbody>
        ${results.map((job) => `<tr data-select="${job.id}" class="${selected?.id === job.id ? "selected" : ""}"><td><strong>${job.company}</strong><span>${job.role}</span></td><td>${job.family}<small>${job.type}</small></td><td>${job.location}<small>${job.mode}</small></td><td>${job.date}</td><td>${sponsorBadge(job)}<small class="evidence-preview">${job.evidence}</small></td><td>${saveButton(job)}</td></tr>`).join("") || `<tr><td colspan="6"><div class="empty-state"><strong>No matching evidence.</strong><p>Clear one filter to continue research.</p></div></td></tr>`}
        </tbody></table></div>
      </main>
      ${details(selected, "inspector")}
    </div>
  </div>`;
}

function renderC() {
  const results = filteredJobs();
  const sections = [
    ["Apply first", "Fresh roles with usable sponsor signals", results.filter((j) => j.urgency === "72h" && j.sponsor !== "no")],
    ["Worth a closer look", "Promising roles that need evidence", results.filter((j) => ["new", "week"].includes(j.urgency) && j.sponsor !== "no")],
    ["Watch the window", "Programs predicted to open later", results.filter((j) => j.urgency === "watch")],
  ];
  app.innerHTML = `<div class="design-c">
    ${commonTop("Opportunity Board", "A calmer daily job ritual", "peach")}
    <main class="board-main">
      <section class="board-welcome"><div><p class="eyebrow">THURSDAY SCAN</p><h1>Your next best roles,<br>already sorted.</h1><p>Prioritize the openings worth your time, then keep moving.</p></div><div class="board-stats"><article><b>${results.length}</b><span>matches</span></article><article><b>${results.filter((j) => j.sponsor === "likely").length}</b><span>sponsor signals</span></article><article><b>${state.saved.size}</b><span>saved</span></article></div></section>
      <section class="board-tools">${searchControl("Search opportunities")}<button class="filter-sheet-button" data-filter-sheet>☷ Filters</button><div class="desktop-chips">${filterChips()}</div></section>
      ${sections.map(([title, subtitle, sectionJobs], index) => sectionJobs.length ? `<section class="board-section"><header><span>0${index + 1}</span><div><h2>${title}</h2><p>${subtitle}</p></div><b>${sectionJobs.length}</b></header><div class="card-grid">${sectionJobs.map((job) => `<article class="opportunity-card" data-select="${job.id}"><div class="card-top"><div class="role-logo">${job.company.slice(0, 2)}</div>${saveButton(job)}</div><small>${job.company} · ${job.date}</small><h3>${job.role}</h3><p>${job.location} · ${job.mode}</p><div class="card-footer"><span>${job.family}</span>${sponsorBadge(job, true)}</div></article>`).join("")}</div></section>` : "").join("") || `<div class="empty-state"><strong>Your board is clear.</strong><p>Try widening the filters to bring opportunities back.</p></div>`}
    </main>
    <div class="mobile-filter-sheet ${state.filterOpen ? "open" : ""}"><div><button class="sheet-close" data-filter-sheet>×</button><p class="eyebrow">FILTER YOUR FEED</p><h2>What belongs on your board?</h2>${filterChips()}<h3>Sponsorship evidence</h3>${sponsorFilters()}<button class="primary-button" data-filter-sheet>Show ${results.length} roles</button></div></div>
    <div class="c-detail-modal ${state.selected ? "open" : ""}"><button class="modal-close" data-close-detail>×</button>${details(jobs.find((job) => job.id === state.selected), "modal")}</div>
  </div>`;
}

function render() {
  if (design === "a") renderA();
  if (design === "b") renderB();
  if (design === "c") renderC();
  bindEvents();
}

function bindEvents() {
  document.querySelectorAll("input[type='search']").forEach((input) => input.addEventListener("input", (event) => { state.query = event.target.value; render(); }));
  document.querySelectorAll("[data-family]").forEach((button) => button.addEventListener("click", () => { state.family = button.dataset.family; render(); }));
  document.querySelectorAll("[data-sponsor]").forEach((button) => button.addEventListener("click", () => { state.sponsor = button.dataset.sponsor; render(); }));
  document.querySelectorAll("[data-cycle-sponsor]").forEach((button) => button.addEventListener("click", () => {
    const values = ["all", "likely", "verify", "unknown", "no"];
    state.sponsor = values[(values.indexOf(state.sponsor) + 1) % values.length]; render();
  }));
  document.querySelectorAll("[data-select]").forEach((element) => element.addEventListener("click", (event) => {
    if (event.target.closest("[data-save]")) return;
    state.selected = Number(element.dataset.select); render();
  }));
  document.querySelectorAll("[data-save]").forEach((button) => button.addEventListener("click", (event) => {
    event.stopPropagation(); const id = Number(button.dataset.save);
    state.saved.has(id) ? state.saved.delete(id) : state.saved.add(id); render();
  }));
  document.querySelectorAll("[data-filter-sheet]").forEach((button) => button.addEventListener("click", () => { state.filterOpen = !state.filterOpen; render(); }));
  document.querySelectorAll("[data-close-detail]").forEach((button) => button.addEventListener("click", () => { state.selected = null; render(); }));
}

render();

"use strict";
// Andy's interface. Data from emails and Donna is untrusted, so the DOM is only ever built with
// h(): strings become text nodes, never HTML. There is no innerHTML anywhere in this file.
(() => {
  const app = document.getElementById("app");
  const nf = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
  const inr = n => (n < 0 ? "−₹" : "₹") + nf.format(Math.abs(Math.round(n || 0)));
  const pct = x => `${Math.round((x || 0) * 100)}%`;
  const todayISO = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  const SVGNS = "http://www.w3.org/2000/svg";

  // ---------------------------------------------------------------- DOM
  function build(ns, tag, attrs, kids) {
    const el = ns ? document.createElementNS(ns, tag) : document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
      else if (k === "text") el.textContent = String(v);
      else if (k === "value" && !ns) el.value = v;
      else if (k === "checked" && !ns) el.checked = !!v;
      else el.setAttribute(k, v === true ? "" : String(v));
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid === null || kid === undefined || kid === false) continue;
      el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return el;
  }
  const h = (tag, attrs, ...kids) => build(null, tag, attrs, kids);
  const s = (tag, attrs, ...kids) => build(SVGNS, tag, attrs, kids);
  const logo = () => document.getElementById("logo-tpl").content.querySelector("svg").cloneNode(true);

  const ICONS = {
    overview: "M3 13h8V3H3zM13 21h8V11h-8zM13 3v6h8V3zM3 21h8v-6H3z",
    expenses: "M3 3v18h18M7 15l4-5 3 3 5-7",
    insights: "M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.4 1 2.5h6c0-1.1.3-1.8 1-2.5A6 6 0 0 0 12 3z",
    approvals: "M9 12l2 2 4-4M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6z",
    tax: "M7 3h10l4 4v14H7zM17 3v4h4M10 12h8M10 16h8",
    info: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
    security: "M6 11h12v10H6zM8 11V7a4 4 0 0 1 8 0v4M12 15v2",
    lock: "M6 11h12v10H6zM8 11V7a4 4 0 0 1 8 0v4",
    plus: "M12 5v14M5 12h14",
    sync: "M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5",
    left: "M15 18l-6-6 6-6",
    right: "M9 18l6-6-6-6",
  };
  const icon = name => s("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" }, s("path", { d: ICONS[name] }));

  // ---------------------------------------------------------------- engine bridge
  async function api(name, ...args) {
    const fn = window.pywebview && window.pywebview.api && window.pywebview.api[name];
    if (!fn) throw new Error("Andy's engine isn't connected.");
    const r = await fn(...args);
    if (!r || !r.ok) throw new Error((r && r.error) || "Something went wrong.");
    return r.data;
  }

  let toastTimer = null;
  function toast(message, bad = false) {
    document.querySelectorAll(".toast").forEach(t => t.remove());
    const t = h("div", { class: `toast${bad ? " bad" : ""}`, role: "status" }, message);
    document.body.append(t);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.remove(), 4200);
  }
  const fail = err => toast(err.message || String(err), true);

  async function busy(button, label, work) {
    const old = button.textContent;
    button.disabled = true;
    button.textContent = label;
    try { return await work(); } finally { button.disabled = false; button.textContent = old; }
  }

  // ---------------------------------------------------------------- state & routing
  const state = { status: null, tab: "overview", recovery: null, expMode: "month", expAnchor: todayISO(),
                  showAdd: false, openTx: null, pairing: null, clock: null };

  async function refreshStatus() { state.status = await api("status"); return state.status; }

  function route() {
    clearInterval(state.clock);
    const st = state.status;
    if (!st.exists) return renderSetup();
    if (!st.unlocked) return renderLock();
    if (state.recovery) return renderRecoveryCode();
    if (!st.onboarded) return renderOnboarding(0);
    return renderShell();
  }

  let lastPing = 0;
  ["pointerdown", "keydown", "wheel"].forEach(evt => document.addEventListener(evt, () => {
    if (!state.status || !state.status.unlocked || Date.now() - lastPing < 20000) return;
    lastPing = Date.now();
    api("ping").catch(() => {});
  }, { passive: true }));

  window.andy = {
    onLocked() {
      if (state.status) state.status.unlocked = false;
      state.pairing = null;
      renderLock("Locked after a period of inactivity.");
    },
    restart() { start(); },
    onDonna(count) {
      toast(`Donna sent ${count} new request${count === 1 ? "" : "s"} for your approval.`);
      if (state.status && state.status.unlocked && state.status.onboarded) renderShell();
    },
  };

  // ---------------------------------------------------------------- shared bits
  function passphraseIssues(p) {
    const issues = [];
    if (p.length < 12) issues.push("at least 12 characters");
    const classes = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter(r => r.test(p)).length;
    if (p.length < 20 && classes < 3) issues.push("mix cases, digits and symbols, or go to 20+ characters");
    if (new Set(p).size < 6) issues.push("more variety");
    return issues;
  }
  function strengthMeter(input) {
    const bar = h("i");
    const hint = h("p", { class: "note" }, "Use a sentence only you would think of, like four unrelated words with a number.");
    input.addEventListener("input", () => {
      const p = input.value, issues = passphraseIssues(p);
      bar.style.width = `${Math.min(100, (p.length / 24) * 100 * (issues.length ? 0.6 : 1))}%`;
      hint.textContent = p ? (issues.length ? `Needs ${issues.join("; ")}.` : "Strong enough. Make sure you can remember it.") :
        "Use a sentence only you would think of, like four unrelated words with a number.";
    });
    return [h("div", { class: "strength" }, bar), hint];
  }
  const field = (label, control, hint) => h("label", { class: "field-row" }, h("span", {}, label), control, hint ? h("small", { class: "note" }, hint) : null);
  const pass = (id, auto = "current-password") => h("input", { class: "input", type: "password", id, autocomplete: auto, spellcheck: "false" });
  const money = (id, value) => h("input", { class: "input money", id, inputmode: "decimal", autocomplete: "off", value: value ? nf.format(value) : "" });
  const readMoney = el => Number(String(el.value).replace(/[^0-9.]/g, "")) || 0;
  const errorLine = () => h("p", { class: "error", role: "alert" });

  function orb() { return h("div", { class: "orb" }, logo()); }

  // ---------------------------------------------------------------- setup
  function renderSetup() {
    const p1 = pass("p1", "new-password"), p2 = pass("p2", "new-password"), err = errorLine();
    const go = h("button", { class: "btn primary", type: "submit" }, "Create my vault");
    const form = h("form", { onsubmit: async e => {
      e.preventDefault();
      err.textContent = "";
      try {
        await busy(go, "Sealing…", async () => {
          const r = await api("create_vault", p1.value, p2.value);
          state.recovery = r.recovery_code;
          await refreshStatus();
          renderRecoveryCode();
        });
      } catch (x) { err.textContent = x.message; }
    } },
      field("Choose a passphrase", p1), ...strengthMeter(p1), field("Type it again", p2), err, go);
    app.replaceChildren(h("div", { class: "gate" }, h("div", { class: "gate-card" },
      orb(),
      h("div", { class: "stack" },
        h("p", { class: "label" }, "First start"),
        h("h1", { class: "title" }, "I'm Andy. Let's seal your vault."),
        h("p", { class: "subtitle" }, "Everything I learn about your money is kept in one encrypted vault on this PC. " +
          "It opens only with your passphrase, and only on this PC and Windows account.")),
      form,
      h("div", { class: "row", style: "justify-content:center" },
        h("span", { class: "pill" }, "AES-256-GCM"), h("span", { class: "pill" }, "scrypt key stretching"),
        h("span", { class: "pill" }, "Bound to this PC"), h("span", { class: "pill" }, "No cloud copy")))));
    p1.focus();
  }

  function renderRecoveryCode() {
    const code = state.recovery, input = h("input", { class: "input num", id: "rc", autocomplete: "off", maxlength: "5", spellcheck: "false" });
    const err = errorLine(), go = h("button", { class: "btn primary", type: "submit" }, "I've written it down");
    const form = h("form", { onsubmit: async e => {
      e.preventDefault();
      try {
        await busy(go, "Checking…", async () => {
          await api("confirm_recovery", input.value);
          state.recovery = null;
          await refreshStatus();
          route();
        });
      } catch (x) { err.textContent = x.message; }
    } }, field("To confirm, type the last 5 characters", input), err, go);
    app.replaceChildren(h("div", { class: "gate" }, h("div", { class: "gate-card" },
      h("p", { class: "label" }, "Recovery code · shown once"),
      h("h1", { class: "title" }, "Write this down on paper."),
      h("p", { class: "subtitle" }, "It is the only way back in if you forget your passphrase or move to a new PC. " +
        "Keep it somewhere safe and offline. Don't photograph it, email it or save it to the cloud."),
      h("div", { class: "recovery", "aria-label": "Recovery code" }, code.split("-").join(" ")),
      form)));
    input.focus();
  }

  // ---------------------------------------------------------------- lock & recover
  function renderLock(message) {
    const p = pass("unlock"), err = errorLine(), go = h("button", { class: "btn primary", type: "submit" }, "Unlock");
    if (message) err.textContent = message;
    const form = h("form", { onsubmit: async e => {
      e.preventDefault();
      err.textContent = "";
      try {
        await busy(go, "Unlocking…", async () => {
          state.status = await api("unlock", p.value);
          p.value = "";
          route();
        });
      } catch (x) { err.textContent = x.message; p.select(); }
    } }, field("Passphrase", p), err, go);
    app.replaceChildren(h("div", { class: "gate" }, h("div", { class: "gate-card" },
      orb(),
      h("div", { class: "stack" }, h("p", { class: "label" }, "Vault sealed"), h("h1", { class: "title" }, "Andy is locked.")),
      form,
      h("button", { class: "link", type: "button", onclick: renderRecover }, "Forgot it? Use your recovery code"))));
    p.focus();
  }

  function renderRecover() {
    const code = h("input", { class: "input num", id: "code", autocomplete: "off", spellcheck: "false", placeholder: "XXXXX-XXXXX-…" });
    const p1 = pass("np1", "new-password"), p2 = pass("np2", "new-password"), err = errorLine();
    const go = h("button", { class: "btn primary", type: "submit" }, "Open and set new passphrase");
    const form = h("form", { onsubmit: async e => {
      e.preventDefault();
      try {
        await busy(go, "Opening…", async () => { state.status = await api("recover", code.value, p1.value, p2.value); route(); });
      } catch (x) { err.textContent = x.message; }
    } }, field("Recovery code", code), field("New passphrase", p1), ...strengthMeter(p1), field("Type it again", p2), err, go);
    app.replaceChildren(h("div", { class: "gate" }, h("div", { class: "gate-card" },
      orb(), h("h1", { class: "title" }, "Recover your vault"),
      h("p", { class: "subtitle" }, "This also moves your vault to this PC if you've copied it from an old one."),
      form, h("button", { class: "link", type: "button", onclick: () => renderLock() }, "Back"))));
    code.focus();
  }

  // ---------------------------------------------------------------- onboarding
  const BUDGET_CATS = ["Groceries", "Food delivery", "Dining out", "Shopping", "Transport", "Fuel", "Bills & utilities", "Subscriptions",
                       "Entertainment", "Health", "Personal care", "Travel", "Education", "Gifts & donations"];
  const EMPLOYMENT = [["salaried", "Salaried"], ["freelancer", "Freelancer / consultant"], ["business", "Business owner"], ["mixed", "A mix"]];
  const STEPS = [
    { title: "Let's get to know you.", intro: "This is how I tailor tax rules and suggestions. You can change anything later in My Info.",
      fields: [["name", "What should I call you?", "text"], ["age", "Age", "int"], ["city", "City", "text"],
               ["employment", "Work", "select", EMPLOYMENT], ["dependents", "People who depend on you", "int"],
               ["metro", "I live in Delhi, Mumbai, Kolkata, Chennai, Bengaluru, Hyderabad, Pune or Ahmedabad", "bool"]] },
    { title: "What comes in.", intro: "Rough numbers are fine. Take-home is what lands in your account each month.",
      fields: [["monthly_take_home", "Monthly take-home pay", "money"], ["annual_gross_salary", "Annual gross salary (from Form 16)", "money"],
               ["basic_da", "Annual basic + DA", "money"], ["other_income_annual", "Other income a year (interest, rent, freelance)", "money"]] },
    { title: "What's already spoken for.", intro: "Fixed monthly commitments, so I can tell them apart from everyday spending.",
      fields: [["monthly_rent", "Rent a month", "money"], ["monthly_emis", "Loan EMIs a month", "money"],
               ["monthly_investments", "SIPs and investments a month", "money"], ["insurance_premiums_annual", "Insurance premiums a year", "money"]] },
    { title: "Your safety net.", intro: "Money set aside for emergencies, and what you've invested so far.",
      fields: [["emergency_fund", "Emergency fund", "money"], ["total_investments", "Total investments (MF, stocks, PF, PPF, NPS)", "money"]] },
    { title: "Taxes.", intro: "You mentioned you've already filed this year. I'll keep that on record.",
      fields: [["itr_filed_fy_2025_26", "I've filed my income-tax return for FY 2025-26", "bool", null, true],
               ["itr_form", "Form filed", "select", [["", "Not sure"], ["ITR-1", "ITR-1"], ["ITR-2", "ITR-2"], ["ITR-3", "ITR-3"], ["ITR-4", "ITR-4"]]],
               ["itr_filed_on", "Filed on", "date"],
               ["itr_outcome", "Outcome", "select", [["", "Choose"], ["refund received", "Refund received"], ["refund pending", "Refund pending"],
                 ["tax paid", "I paid tax"], ["nil", "Nothing due either way"], ["not sure", "Not sure"]]],
               ["tax_regime", "Regime for this year", "select", [["new", "New regime"], ["old", "Old regime"]]]] },
    { title: "A spending plan.", intro: "Budgets let me warn you early. I've suggested a starting point from your take-home pay.", budgets: true },
    { title: "Connect Gmail.", intro: "I read bank, card and UPI alert emails to track every expense day by day. Read-only: I never send, move or delete mail.", gmail: true },
    { title: "What are you working towards?", intro: "A home, a car, travel, early retirement? A sentence is enough.",
      fields: [["goals", "Your goals", "textarea"]] },
  ];

  function control(spec, profile) {
    const [key, label, kind, options, fallback] = spec;
    const value = profile[key] !== undefined ? profile[key] : fallback;
    if (kind === "bool") return h("label", { class: "check", style: "grid-column:1/-1" }, h("input", { type: "checkbox", id: `f-${key}`, checked: !!value }), label);
    let input;
    if (kind === "select") input = h("select", { class: "input", id: `f-${key}` }, options.map(([v, t]) => h("option", { value: v, selected: v === (value || "") ? "selected" : null }, t)));
    else if (kind === "money") input = money(`f-${key}`, value);
    else if (kind === "textarea") input = h("textarea", { class: "input", id: `f-${key}`, maxlength: "500" }, value || "");
    else input = h("input", { class: kind === "int" ? "input num" : "input", id: `f-${key}`, type: kind === "date" ? "date" : "text",
      inputmode: kind === "int" ? "numeric" : null, value: value === undefined || value === null ? "" : value, autocomplete: "off" });
    return h("label", { class: "field-row", style: kind === "textarea" ? "grid-column:1/-1" : null }, h("span", {}, label), input);
  }
  function collect(fields) {
    const out = {};
    for (const [key, , kind] of fields) {
      const el = document.getElementById(`f-${key}`);
      if (!el) continue;
      out[key] = kind === "bool" ? el.checked : kind === "money" ? readMoney(el) : el.value;
    }
    return out;
  }

  async function renderOnboarding(index) {
    const step = STEPS[index];
    let info;
    try { info = await api("get_profile"); } catch (x) { return fail(x); }
    const profile = info.profile || {}, err = errorLine();
    const body = h("div", { class: "form-grid" });
    let budgetInputs = {}, totalInput = null;
    if (step.fields) body.append(...step.fields.map(f => control(f, profile)));
    if (step.budgets) {
      const suggested = await api("suggested_budgets").catch(() => ({}));
      const current = Object.keys(info.budgets || {}).length ? info.budgets : suggested;
      totalInput = money("f-monthly_budget", profile.monthly_budget || Object.values(current).reduce((a, b) => a + b, 0));
      body.append(field("Total monthly spending budget", totalInput, "Excluding rent, EMIs and investments."));
      for (const c of BUDGET_CATS) {
        budgetInputs[c] = money(`b-${c}`, current[c]);
        body.append(field(c, budgetInputs[c]));
      }
    }
    if (step.gmail) body.append(gmailConnectForm(info.gmail, () => renderOnboarding(index + 1)));

    const next = h("button", { class: "btn primary", type: "button" }, index === STEPS.length - 1 ? "Finish" : "Continue");
    next.addEventListener("click", async () => {
      err.textContent = "";
      try {
        await busy(next, "Saving…", async () => {
          if (step.fields) await api("save_profile", collect(step.fields));
          if (step.budgets) {
            await api("save_profile", { monthly_budget: readMoney(totalInput) });
            const b = {};
            for (const [c, el] of Object.entries(budgetInputs)) b[c] = readMoney(el);
            await api("save_budgets", b);
          }
          if (index === STEPS.length - 1) { state.status = await api("finish_onboarding"); state.tab = "overview"; route(); }
          else renderOnboarding(index + 1);
        });
      } catch (x) { err.textContent = x.message; }
    });
    const back = index ? h("button", { class: "btn ghost", type: "button", onclick: () => renderOnboarding(index - 1) }, "Back") : h("span");
    app.replaceChildren(h("div", { class: "gate" }, h("div", { class: "gate-card wide" },
      h("div", { class: "row" }, h("div", { class: "brand" }, logo(), h("div", {}, h("div", { class: "wordmark" }, "Andy"), h("small", {}, "First start"))),
        h("span", { class: "pill", style: "margin-left:auto" }, `${index + 1} / ${STEPS.length}`)),
      h("div", { class: "steps" }, STEPS.map((_, i) => h("i", { class: i <= index ? "on" : null }))),
      h("div", { class: "panel hud stack" }, h("h1", { class: "title" }, step.title), h("p", { class: "subtitle" }, step.intro), body, err),
      h("div", { class: "wizard-nav" }, back, h("div", { class: "row" },
        step.gmail ? h("button", { class: "btn ghost", type: "button", onclick: () => renderOnboarding(index + 1) }, "Skip for now") : null, next)))));
    const first = body.querySelector("input, select, textarea");
    if (first) first.focus();
  }

  function gmailConnectForm(g, after) {
    if (g && g.connected) return h("div", { class: "stack", style: "grid-column:1/-1" }, h("p", {}, h("span", { class: "pill good" }, h("i", { class: "dot" }), "Connected"), " ", g.address));
    const addr = h("input", { class: "input", id: "g-addr", type: "email", autocomplete: "off", placeholder: "you@gmail.com", value: (g && g.address) || "" });
    const pw = h("input", { class: "input num", id: "g-pw", type: "password", autocomplete: "off", placeholder: "16-letter app password" });
    const err = errorLine(), go = h("button", { class: "btn", type: "button" }, "Connect Gmail");
    go.addEventListener("click", async () => {
      err.textContent = "";
      try {
        await busy(go, "Checking with Gmail…", async () => { await api("gmail_connect", addr.value, pw.value); pw.value = ""; toast("Gmail connected, read-only."); });
        if (after) after();
      } catch (x) { err.textContent = x.message; }
    });
    return h("div", { class: "stack", style: "grid-column:1/-1" },
      h("ol", { class: "dim", style: "margin:0;padding-left:20px;display:grid;gap:6px" },
        h("li", {}, "Turn on 2-Step Verification for your Google account."),
        h("li", {}, "Create an app password named “Andy” at myaccount.google.com/apppasswords. ",
          h("button", { class: "link", type: "button", onclick: () => api("open_link", "apppasswords").catch(fail) }, "Open it")),
        h("li", {}, "Paste the 16 letters below. Andy stores them inside the encrypted vault.")),
      h("div", { class: "form-grid" }, field("Gmail address", addr), field("App password", pw)), err, h("div", {}, go));
  }

  // ---------------------------------------------------------------- shell
  const TABS = [["overview", "Overview"], ["expenses", "Expenses"], ["insights", "Insights"], ["approvals", "Approvals"],
                ["tax", "Tax"], ["info", "My info"], ["security", "Security"]];

  async function renderShell() {
    let pending = 0;
    try { pending = (await api("donna_requests")).requests.filter(r => r.status === "pending").length; } catch (x) { /* shown later */ }
    const nav = h("nav", { class: "nav", "aria-label": "Sections" }, TABS.map(([key, label]) => h("button", {
      type: "button", "aria-current": state.tab === key ? "page" : null,
      onclick: () => { state.tab = key; state.openTx = null; renderShell(); } },
      icon(key), label, key === "approvals" && pending ? h("span", { class: "badge" }, pending) : null)));
    const main = h("section", { class: "main" }, h("p", { class: "faint" }, "Loading…"));
    const rail = h("aside", { class: "rail" },
      h("div", { class: "brand" }, logo(), h("div", {}, h("div", { class: "wordmark" }, "Andy"), h("small", {}, "Personal CA · Expense guardian"))),
      nav,
      h("div", { class: "rail-foot" },
        h("div", { class: "seal" }, h("i", { class: "dot" }), state.status.dev_mode ? "Dev mode · test data only" : "Vault sealed on this PC"),
        h("button", { class: "btn", type: "button", onclick: lockNow }, icon("lock"), "Lock")));
    app.replaceChildren(h("div", { class: "shell" }, rail, main));
    const render = { overview: tabOverview, expenses: tabExpenses, insights: tabInsights, approvals: tabApprovals,
                     tax: tabTax, info: tabInfo, security: tabSecurity }[state.tab];
    try { await render(main); } catch (x) { main.replaceChildren(h("div", { class: "panel" }, h("p", { class: "error" }, x.message))); }
  }

  async function lockNow() {
    try { state.status = await api("lock"); state.pairing = null; renderLock(); } catch (x) { fail(x); }
  }

  function topbar(title, ...actions) {
    const clock = h("p", { class: "clock" });
    const tick = () => { clock.textContent = new Date().toLocaleString("en-IN", { weekday: "long", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).toUpperCase(); };
    tick();
    clearInterval(state.clock);
    state.clock = setInterval(tick, 15000);
    return h("header", { class: "topbar" }, h("div", { class: "stack", style: "gap:6px" }, clock, h("h1", {}, title)), h("div", { class: "row" }, actions));
  }

  function greeting() {
    const hr = new Date().getHours();
    const part = hr < 5 ? "Still up" : hr < 12 ? "Good morning" : hr < 17 ? "Good afternoon" : "Good evening";
    return state.status.name ? `${part}, ${state.status.name}.` : `${part}.`;
  }

  function syncButton(after) {
    const b = h("button", { class: "btn", type: "button" }, icon("sync"), "Sync Gmail");
    b.addEventListener("click", async () => {
      try {
        const r = await busy(b, "Reading alerts…", () => api("gmail_sync"));
        let msg = `${r.added} new transaction${r.added === 1 ? "" : "s"} from ${r.new} alert email${r.new === 1 ? "" : "s"}.`;
        if (r.failed_authentication) msg += ` ${r.failed_authentication} email(s) failed bank authentication and were ignored.`;
        toast(msg);
        if (after) after();
      } catch (x) { fail(x); }
    });
    return b;
  }
  function addButton(after) {
    return h("button", { class: "btn", type: "button", onclick: () => { state.showAdd = !state.showAdd; after(); } }, icon("plus"), "Add expense");
  }

  // ---------------------------------------------------------------- charts
  function shortInr(n) {
    const a = Math.abs(n);
    if (a >= 1e7) return `₹${(n / 1e7).toFixed(1)}Cr`;
    if (a >= 1e5) return `₹${(n / 1e5).toFixed(1)}L`;
    if (a >= 1e3) return `₹${(n / 1e3).toFixed(a >= 1e4 ? 0 : 1)}k`;
    return `₹${Math.round(n)}`;
  }
  function niceMax(v) {
    const p = Math.pow(10, Math.floor(Math.log10(Math.max(v, 1))));
    for (const m of [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
    return 10 * p;
  }
  function barChart(host, series, { label, title, selected, onPick, budget, height = 190 }) {
    const W = Math.max(300, Math.round(host.clientWidth || 640)), H = height, padL = 52, padB = 24, padT = 10;
    const max = niceMax(Math.max(1, budget || 0, ...series.map(d => d.total)));
    const plotW = W - padL, plotH = H - padB - padT, bw = plotW / series.length;
    const y = v => padT + plotH - (Math.max(0, v) / max) * plotH;
    const every = Math.max(1, Math.ceil(series.length / Math.floor(plotW / 34)));
    const svg = s("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": title || "Spending chart" },
      s("defs", {}, s("linearGradient", { id: "andy-bar", x1: "0", y1: "0", x2: "0", y2: "1" },
        s("stop", { offset: "0", "stop-color": "#8FF3FF" }), s("stop", { offset: "1", "stop-color": "#B9A4FF", "stop-opacity": "0.55" }))),
      [0, 0.5, 1].map(f => [s("line", { class: "grid-line", x1: padL, x2: W, y1: y(max * f), y2: y(max * f) }),
        s("text", { class: "axis", x: padL - 8, y: y(max * f) + 3.5, "text-anchor": "end" }, shortInr(max * f))]),
      budget ? s("line", { class: "budget-line", x1: padL, x2: W, y1: y(budget), y2: y(budget) }) : null,
      series.map((d, i) => {
        const x = padL + i * bw, w = Math.max(2, bw * 0.62), top = y(d.total), hgt = Math.max(d.total > 0 ? 2 : 1.5, padT + plotH - top);
        return s("g", {},
          s("rect", { class: "hit", x, y: padT, width: bw, height: plotH + padB, onclick: onPick ? () => onPick(d, i) : null }),
          s("rect", { class: `bar${d.total > 0 ? "" : " zero"}${selected === i ? " sel" : ""}`, x: x + (bw - w) / 2, y: padT + plotH - hgt, width: w, height: hgt, rx: Math.min(3, w / 2) },
            s("title", {}, `${label(d, i, true)}: ${inr(d.total)}`)),
          i % every === 0 ? s("text", { class: "axis", x: x + bw / 2, y: H - 6, "text-anchor": "middle" }, label(d, i, false)) : null);
      }));
    host.replaceChildren(svg);
  }
  function mountChart(panel, ...args) {
    const host = h("div", { style: "min-width:0" });
    panel.append(host);
    requestAnimationFrame(() => barChart(host, ...args));
  }

  function ring(fraction) {
    const r = 60, c = 2 * Math.PI * r, f = Math.min(1, fraction || 0), over = (fraction || 0) > 1;
    return s("svg", { class: "ring", viewBox: "0 0 150 150", role: "img", "aria-label": `${pct(fraction)} of the monthly budget used` },
      s("defs", {}, s("linearGradient", { id: "andy-ring", x1: "0", y1: "0", x2: "1", y2: "1" },
        s("stop", { offset: "0", "stop-color": "#8FF3FF" }), s("stop", { offset: ".6", "stop-color": "#B9A4FF" }), s("stop", { offset: "1", "stop-color": "#FFD8A8" }))),
      s("circle", { cx: 75, cy: 75, r, fill: "none", stroke: "rgba(170,200,255,0.12)", "stroke-width": 8 }),
      s("circle", { cx: 75, cy: 75, r, fill: "none", stroke: over ? "#FF8A9B" : "url(#andy-ring)", "stroke-width": 8, "stroke-linecap": "round",
        "stroke-dasharray": `${c * f} ${c}`, transform: "rotate(-90 75 75)" }),
      s("text", { x: 75, y: 78, "text-anchor": "middle", fill: "#E9EEF8", "font-size": 30, "font-weight": 300 }, pct(fraction)),
      s("text", { x: 75, y: 98, "text-anchor": "middle", fill: "#66728A", "font-size": 10, "letter-spacing": "2" }, "OF BUDGET"));
  }

  function hbars(rows, budgets) {
    const limit = Object.fromEntries((budgets || []).map(b => [b.category, b.limit]));
    const max = Math.max(1, ...rows.map(r => Math.max(r.total, limit[r.category] || 0)));
    return h("div", { class: "hbars" }, rows.map(r => {
      const over = limit[r.category] && r.total > limit[r.category];
      return h("div", { class: "hbar" },
        h("span", {}, r.category, h("span", { class: "faint" }, ` · ${r.count}`)),
        h("span", { class: `num${over ? " warn" : ""}` }, inr(r.total), limit[r.category] ? h("span", { class: "faint" }, ` / ${inr(limit[r.category])}`) : null),
        h("div", { class: "track" }, h("div", { class: `fill${over ? " over" : ""}`, style: `width:${(r.total / max) * 100}%` })));
    }));
  }

  // ---------------------------------------------------------------- transactions
  const glyphFor = c => (c || "?").split(/[\s&]+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();
  function txList(txns, categories, refresh) {
    if (!txns.length) return h("div", { class: "empty" }, "No transactions here.");
    return h("div", { class: "tx-list" }, txns.map(t => {
      const open = state.openTx === t.id;
      const sign = t.direction === "credit" ? "+" : "−";
      const amtClass = t.excluded || ["Transfers", "Investments"].includes(t.category) ? "amt muted" : t.direction === "credit" ? "amt credit" : "amt";
      const row = h("div", { class: "tx", role: "button", tabindex: "0", "aria-expanded": open ? "true" : "false",
        onclick: e => { if (e.target.closest(".tx-edit")) return; state.openTx = open ? null : t.id; refresh(); },
        onkeydown: e => { if ((e.key === "Enter" || e.key === " ") && !e.target.closest(".tx-edit")) { e.preventDefault(); state.openTx = open ? null : t.id; refresh(); } } },
        h("div", { class: "glyph" }, glyphFor(t.category)),
        h("div", { class: "who" }, h("b", {}, t.merchant),
          h("small", {}, [t.category, t.mode, t.account, `${t.date}${t.time ? " " + t.time : ""}`].filter(Boolean).join(" · "))),
        h("div", { class: amtClass }, `${sign}${inr(t.amount)}`));
      if (open) row.append(txEditor(t, categories, refresh));
      return row;
    }));
  }
  function txEditor(t, categories, refresh) {
    const all = categories.concat(["Investments", "Transfers"]);
    const cat = h("select", { class: "input", "aria-label": "Category" }, all.map(c => h("option", { value: c, selected: c === t.category ? "selected" : null }, c)));
    const remember = h("input", { type: "checkbox" });
    const note = h("input", { class: "input", placeholder: "Note", value: t.note || "", maxlength: "200", style: "max-width:260px;min-height:32px;padding:4px 10px" });
    const save = h("button", { class: "btn sm", type: "button" }, "Save");
    save.addEventListener("click", async () => {
      try { await api("update_transaction", t.id, { category: cat.value, remember: remember.checked, note: note.value }); state.openTx = null; toast("Saved."); refresh(); } catch (x) { fail(x); }
    });
    const exclude = h("button", { class: "btn sm ghost", type: "button" }, t.excluded ? "Count it again" : "Don't count this");
    exclude.addEventListener("click", async () => { try { await api("update_transaction", t.id, { excluded: !t.excluded }); refresh(); } catch (x) { fail(x); } });
    const del = h("button", { class: "btn sm danger ghost", type: "button" }, "Delete");
    del.addEventListener("click", async () => {
      if (del.dataset.armed !== "1") { del.dataset.armed = "1"; del.textContent = "Tap again to delete"; return; }
      try { await api("delete_transaction", t.id); state.openTx = null; refresh(); } catch (x) { fail(x); }
    });
    return h("div", { class: "tx-edit" }, cat, h("label", { class: "check note" }, remember, `Always for ${t.merchant}`), note, save, exclude, del,
      t.context ? h("p", { class: "note", style: "flex-basis:100%" }, `From the alert: “${t.context}”`) : null);
  }
  function addExpensePanel(categories, done) {
    const amount = money("a-amt"), when = h("input", { class: "input", type: "date", id: "a-date", value: todayISO() });
    const who = h("input", { class: "input", id: "a-who", placeholder: "Where or who", maxlength: "60" });
    const cat = h("select", { class: "input", id: "a-cat" }, h("option", { value: "" }, "Let Andy decide"), categories.map(c => h("option", { value: c }, c)));
    const note = h("input", { class: "input", id: "a-note", maxlength: "200" });
    const err = errorLine(), go = h("button", { class: "btn primary", type: "button" }, "Add");
    go.addEventListener("click", async () => {
      try {
        await api("add_transaction", { amount: readMoney(amount), date: when.value, merchant: who.value, category: cat.value, note: note.value });
        state.showAdd = false; toast("Added."); done();
      } catch (x) { err.textContent = x.message; }
    });
    return h("div", { class: "panel hud stack" }, h("p", { class: "label" }, "New expense"),
      h("div", { class: "form-grid" }, field("Amount", amount), field("Date", when), field("Paid to", who), field("Category", cat), field("Note", note)),
      err, h("div", { class: "row" }, go, h("button", { class: "btn ghost", type: "button", onclick: () => { state.showAdd = false; done(); } }, "Cancel")));
  }

  // ---------------------------------------------------------------- overview
  async function tabOverview(main) {
    const [o, info] = await Promise.all([api("overview"), api("get_profile")]);
    const again = () => tabOverview(main);
    const actions = [o.gmail.connected ? syncButton(again) : null, addButton(again)];
    const delta = o.prev_month_same_point ? (o.spent_month - o.prev_month_same_point) / o.prev_month_same_point : null;
    const heroLeft = h("div", { class: "panel hud" }, h("div", { class: "hero-main" },
      o.monthly_budget ? ring(o.budget_used) : null,
      h("div", { class: "stat" }, h("p", { class: "label" }, "Spent this month"), h("p", { class: "figure" }, inr(o.spent_month)),
        delta === null ? h("p", { class: "delta faint" }, "No comparison with last month yet") :
          h("p", { class: `delta ${delta > 0 ? "warn" : "good"}` }, `${delta > 0 ? "▲" : "▼"} ${pct(Math.abs(delta))} vs this point last month`),
        o.monthly_budget ? h("p", { class: "dim" }, `${inr(Math.max(0, o.monthly_budget - o.budget_spent))} left of your ${inr(o.monthly_budget)} everyday budget`) :
          h("p", { class: "dim" }, "Set a monthly budget in My Info to track it here."))));
    const heroRight = h("div", { class: "grid g-2" },
      tile("Today", inr(o.spent_today)), tile("Last 7 days", inr(o.spent_week)),
      tile("Month-end pace", inr(o.projected_month), o.monthly_budget && o.projected_month > o.monthly_budget ? "warn" : null),
      tile("Pace leaves you", o.projected_savings === null ? "—" : inr(o.projected_savings), o.projected_savings !== null && o.projected_savings < 0 ? "bad" : "good"));
    main.replaceChildren(topbar(greeting(), ...actions));
    if (state.showAdd) main.append(addExpensePanel(info.categories, again));
    if (!o.transaction_count) {
      main.append(h("div", { class: "panel hud empty" }, h("h2", { class: "title" }, "Nothing tracked yet."),
        h("p", { class: "subtitle" }, o.gmail.connected ? "Sync Gmail to pull in your bank, card and UPI alerts." : "Connect Gmail in My Info and I'll pull in every bank, card and UPI alert, or add an expense by hand."),
        h("div", { class: "row" }, actions)));
      return;
    }
    main.append(h("div", { class: "hero" }, heroLeft, heroRight));
    if (o.donna_pending) main.append(h("button", { class: "panel hud row", type: "button", style: "text-align:left;cursor:pointer", onclick: () => { state.tab = "approvals"; renderShell(); } },
      h("span", { class: "pill iris-pill" }, `${o.donna_pending} waiting`), h("span", {}, "Donna has asked for your approval. You have the final say.")));

    const daily = h("div", { class: "panel" }, h("div", { class: "panel-head" }, h("p", { class: "label" }, "Day by day · last 30 days"),
      h("span", { class: "note" }, "Tap a day to see it")));
    mountChart(daily, o.last_30_days, { title: "Spending per day, last 30 days",
      label: (d, i, full) => full ? d.date : String(Number(d.date.slice(8))),
      onPick: d => { state.tab = "expenses"; state.expMode = "day"; state.expAnchor = d.date; renderShell(); } });

    const cats = h("div", { class: "panel" }, h("div", { class: "panel-head" }, h("p", { class: "label" }, "Where it went this month")),
      o.categories.length ? hbars(o.categories.slice(0, 7), o.budgets) : h("p", { class: "dim" }, "No spending this month yet."));

    const tips = o.insights.items.slice(0, 3);
    const advice = h("div", { class: "panel hud" }, h("div", { class: "panel-head" }, h("p", { class: "label" }, "Andy suggests"),
      o.insights.total_monthly ? h("span", { class: "iris num" }, `up to ${inr(o.insights.total_monthly)}/month`) : null),
      tips.length ? h("div", {}, tips.map(suggestion)) : h("p", { class: "dim" }, "Nothing to flag yet. I need a few weeks of transactions to spot patterns."),
      tips.length ? h("button", { class: "link", type: "button", onclick: () => { state.tab = "insights"; renderShell(); } }, "See every suggestion") : null);

    const recent = h("div", { class: "panel" }, h("div", { class: "panel-head" }, h("p", { class: "label" }, "Latest"),
      h("button", { class: "link", type: "button", onclick: () => { state.tab = "expenses"; renderShell(); } }, "All expenses")),
      txList(o.recent, info.categories, again));
    main.append(daily, h("div", { class: "grid g-2" }, cats, advice), recent);
  }
  const tile = (label, value, tone) => h("div", { class: "panel stat" }, h("p", { class: "label" }, label), h("p", { class: `figure sm${tone ? " " + tone : ""}` }, value));
  function suggestion(sg) {
    return h("div", { class: "suggestion" }, h("h3", {}, sg.title), h("p", {}, sg.detail),
      h("div", { class: "save" }, sg.monthly_saving ? [h("b", { class: "iris" }, inr(sg.monthly_saving)), h("span", { class: "note" }, sg.one_time ? "this month" : "a month")] : h("span", { class: "note" }, "visibility")),
      h("p", { class: "basis" }, sg.basis));
  }

  // ---------------------------------------------------------------- expenses
  function shiftAnchor(delta) {
    const d = new Date(state.expAnchor + "T00:00:00");
    if (state.expMode === "day") d.setDate(d.getDate() + delta);
    else if (state.expMode === "month") { d.setDate(1); d.setMonth(d.getMonth() + delta); }
    else d.setFullYear(d.getFullYear() + delta);
    const iso = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    state.expAnchor = iso > todayISO() && state.expMode === "day" ? todayISO() : iso;
  }

  async function tabExpenses(main) {
    const [v, info] = await Promise.all([api("view", state.expMode, state.expAnchor), api("get_profile")]);
    const again = () => tabExpenses(main);
    const seg = h("div", { class: "seg", role: "group", "aria-label": "View" }, [["day", "Day"], ["month", "Month"], ["year", "Year"]].map(([k, t]) =>
      h("button", { type: "button", "aria-pressed": state.expMode === k ? "true" : "false", onclick: () => { state.expMode = k; state.openTx = null; again(); } }, t)));
    const label = v.mode === "day" ? new Date(v.anchor + "T00:00:00").toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" }) : v.label;
    const navRow = h("div", { class: "row" }, seg,
      h("div", { class: "row", style: "gap:4px" },
        h("button", { class: "btn sm", type: "button", "aria-label": "Previous", onclick: () => { shiftAnchor(-1); again(); } }, icon("left")),
        h("span", { class: "num", style: "min-width:12ch;text-align:center" }, label),
        h("button", { class: "btn sm", type: "button", "aria-label": "Next", onclick: () => { shiftAnchor(1); again(); } }, icon("right"))),
      h("button", { class: "btn sm ghost", type: "button", onclick: () => { state.expAnchor = todayISO(); again(); } }, "Today"));
    main.replaceChildren(topbar("Expenses", info.gmail.connected ? syncButton(again) : null, addButton(again)), navRow);
    if (state.showAdd) main.append(addExpensePanel(info.categories, again));

    if (v.mode === "day") {
      const chart = h("div", { class: "panel" }, h("div", { class: "panel-head" }, h("p", { class: "label" }, "30 days to this date"), h("span", { class: "note" }, "Tap a bar to jump")));
      mountChart(chart, v.series, { title: "Daily spending", selected: v.series.length - 1,
        label: (d, i, full) => full ? d.date : String(Number(d.date.slice(8))), onPick: d => { state.expAnchor = d.date; again(); } });
      main.append(h("div", { class: "grid g-3" }, tile("Spent this day", inr(v.total)), tile("Transactions", String(v.transactions.length)),
        tile("Biggest category", v.categories[0] ? v.categories[0].category : "—")), chart,
        h("div", { class: "panel" }, h("p", { class: "label", style: "margin-bottom:8px" }, "Transactions"), txList(v.transactions, info.categories, again)));
    } else if (v.mode === "month") {
      const change = v.previous_total ? (v.total - v.previous_total) / v.previous_total : null;
      const chart = h("div", { class: "panel" }, h("div", { class: "panel-head" }, h("p", { class: "label" }, "Every day this month"), h("span", { class: "note" }, "Tap a day for detail")));
      const dailyBudget = info.profile.monthly_budget ? info.profile.monthly_budget / v.series.length : null;
      mountChart(chart, v.series, { title: "Daily spending this month", budget: dailyBudget,
        label: (d, i, full) => full ? d.date : String(Number(d.date.slice(8))), onPick: d => { state.expMode = "day"; state.expAnchor = d.date; again(); } });
      main.append(h("div", { class: "grid g-4" }, tile("Spent", inr(v.total)),
        tile(v.in_progress ? "vs same days last month" : "vs last month", change === null ? "—" : `${change > 0 ? "+" : "−"}${pct(Math.abs(change))}`, change > 0 ? "warn" : "good"),
        tile("Income seen", inr(v.income)), tile(v.in_progress ? "Kept of income so far" : "Kept of income", v.income ? pct((v.income - v.total) / v.income) : "—")), chart,
        h("div", { class: "grid g-2" },
          h("div", { class: "panel" }, h("p", { class: "label", style: "margin-bottom:12px" }, "By category"), v.categories.length ? hbars(v.categories, v.budgets) : h("p", { class: "dim" }, "Nothing yet.")),
          h("div", { class: "panel" }, h("p", { class: "label", style: "margin-bottom:12px" }, "Top merchants"), merchantTable(v.merchants))),
        h("div", { class: "panel" }, h("p", { class: "label", style: "margin-bottom:8px" }, `All transactions · ${v.transactions.length}`), txList(v.transactions, info.categories, again)));
    } else {
      const change = v.previous_total ? (v.total - v.previous_total) / v.previous_total : null;
      const chart = h("div", { class: "panel" }, h("div", { class: "panel-head" }, h("p", { class: "label" }, "Month by month"), h("span", { class: "note" }, "Tap a month for detail")));
      mountChart(chart, v.series, { title: "Monthly spending", height: 220,
        label: (d, i, full) => full ? d.month : new Date(d.month + "-01T00:00:00").toLocaleDateString("en-IN", { month: "short" }),
        onPick: d => { state.expMode = "month"; state.expAnchor = d.month + "-01"; again(); } });
      const active = v.series.filter(m => m.total > 0).length;
      main.append(h("div", { class: "grid g-4" }, tile("Spent this year", inr(v.total)),
        tile("vs last year", change === null ? "—" : `${change > 0 ? "+" : "−"}${pct(Math.abs(change))}`, change > 0 ? "warn" : "good"),
        tile("Monthly average", inr(active ? v.total / active : 0)), tile("Income seen", inr(v.income))), chart,
        h("div", { class: "grid g-2" },
          h("div", { class: "panel" }, h("p", { class: "label", style: "margin-bottom:12px" }, "By category"), v.categories.length ? hbars(v.categories) : h("p", { class: "dim" }, "Nothing yet.")),
          h("div", { class: "panel" }, h("p", { class: "label", style: "margin-bottom:12px" }, "Top merchants"), merchantTable(v.merchants))));
    }
  }
  function merchantTable(rows) {
    if (!rows.length) return h("p", { class: "dim" }, "Nothing yet.");
    return h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Merchant"), h("th", { class: "num" }, "Times"), h("th", { class: "num" }, "Total"))),
      h("tbody", {}, rows.map(r => h("tr", {}, h("td", {}, r.merchant), h("td", { class: "num" }, r.count), h("td", { class: "num" }, inr(r.total)))))));
  }

  // ---------------------------------------------------------------- insights
  async function tabInsights(main) {
    const ins = await api("insights");
    main.replaceChildren(topbar("Ways to spend less"));
    main.append(h("div", { class: "grid g-2" },
      h("div", { class: "panel hud stat" }, h("p", { class: "label" }, "Possible saving a month"), h("p", { class: "figure iris" }, inr(ins.total_monthly))),
      h("div", { class: "panel hud stat" }, h("p", { class: "label" }, "Over a year"), h("p", { class: "figure" }, inr(ins.total_monthly * 12)))));
    main.append(h("div", { class: "panel" }, ins.items.length ? ins.items.map(suggestion) :
      h("div", { class: "empty" }, h("p", {}, "Nothing to flag yet."), h("p", { class: "note" }, "Suggestions appear once Andy has a few weeks of your transactions."))));
    if (ins.subscriptions.length) main.append(h("div", { class: "panel" }, h("p", { class: "label", style: "margin-bottom:12px" }, "Recurring charges Andy found"),
      h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Merchant"), h("th", {}, "Category"), h("th", { class: "num" }, "Months seen"), h("th", {}, "Last charged"), h("th", { class: "num" }, "A month"))),
        h("tbody", {}, ins.subscriptions.map(r => h("tr", {}, h("td", {}, r.merchant), h("td", { class: "dim" }, r.category), h("td", { class: "num" }, r.months_seen), h("td", { class: "num" }, r.last), h("td", { class: "num" }, inr(r.monthly)))))))));
  }

  // ---------------------------------------------------------------- approvals (Donna)
  async function tabApprovals(main) {
    await api("donna_check").catch(() => {});
    const d = await api("donna_requests");
    const again = () => tabApprovals(main);
    main.replaceChildren(topbar("Approvals"));
    main.append(h("div", { class: "panel hud row", style: "justify-content:space-between" },
      h("div", { class: "stack", style: "gap:4px" }, h("p", { class: "label" }, "Donna"),
        h("p", {}, d.paired ? "Connected through an encrypted local channel. Donna can only ask; you decide." : "Not connected. Pair Donna in Security.")),
      h("span", { class: `pill ${d.paired ? "good" : ""}` }, h("i", { class: "dot" }), d.paired ? "Paired" : "Not paired")));
    const pending = d.requests.filter(r => r.status === "pending"), done = d.requests.filter(r => r.status !== "pending");
    main.append(h("div", { class: "panel" }, h("p", { class: "label", style: "margin-bottom:12px" }, `Waiting for you · ${pending.length}`),
      pending.length ? h("div", { class: "stack" }, pending.map(r => requestCard(r, d.threshold, again))) : h("p", { class: "dim" }, "Nothing waiting.")));
    main.append(h("div", { class: "panel stack" }, h("p", { class: "label" }, "Paying for what you approve"),
      h("p", { class: "dim" }, "Andy never moves money and never sees your UPI PIN. When you approve, Donna is told yes, and you pay in your UPI app as usual. " +
        "The payment then shows up here from your bank's alert email. Banks and UPI apps don't offer a personal connection for reading or paying, so this keeps your PIN as the final lock.")));
    if (done.length) main.append(h("div", { class: "panel" }, h("p", { class: "label", style: "margin-bottom:12px" }, "Decided"),
      h("div", { class: "table-wrap" }, h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Request"), h("th", {}, "Decision"), h("th", {}, "When"))),
        h("tbody", {}, done.slice(0, 30).map(r => h("tr", {}, h("td", {}, r.type === "expense_request" ? `${inr(r.amount)} · ${r.payee}` : `Summary · ${r.period.replace("_", " ")}`),
          h("td", {}, h("span", { class: `pill ${r.status === "approved" ? "good" : "bad"}` }, r.status)), h("td", { class: "num dim" }, (r.decided_at || "").replace("T", " ")))))))));
  }
  function requestCard(r, threshold, after) {
    const note = h("input", { class: "input", placeholder: "Note for Donna (optional)", maxlength: "200" });
    const pp = r.needs_passphrase ? pass(`pp-${r.id}`) : null;
    const err = errorLine();
    const decide = decision => async () => {
      try { await api("donna_decide", r.id, decision, note.value, pp ? pp.value : null); toast(decision === "approved" ? "Approved. Donna has been told." : "Rejected. Donna has been told."); after(); }
      catch (x) { err.textContent = x.message; }
    };
    const head = r.type === "expense_request" ?
      [h("p", { class: "label" }, "Donna asks to spend"), h("p", { class: "amount num" }, inr(r.amount)),
        h("p", {}, h("b", {}, r.payee), h("span", { class: "dim" }, ` · ${r.purpose}`)),
        h("p", { class: "note" }, [r.category, r.due ? `due ${r.due}` : null, `sent ${new Date(r.sent * 1000).toLocaleString("en-IN")}`].filter(Boolean).join(" · "))] :
      [h("p", { class: "label" }, "Donna asks for a spending summary"), h("p", {}, `Period: ${r.period.replace("_", " ")}`), h("p", { class: "dim" }, `Reason: ${r.reason}`),
        r.share_preview ? h("div", { class: "mono-block" }, `Would share: total ${inr(r.share_preview.total_spent)}; ` +
          r.share_preview.by_category.map(c => `${c.category} ${inr(c.total)}`).join(", ")) : null];
    return h("div", { class: "request" }, ...head, h("div", { class: "form-grid" }, note,
      pp ? field(`Passphrase (required above ${inr(threshold)})`, pp) : null), err,
      h("div", { class: "row" }, h("button", { class: "btn primary", type: "button", onclick: decide("approved") }, r.type === "expense_request" ? "Approve" : "Share it"),
        h("button", { class: "btn danger", type: "button", onclick: decide("rejected") }, r.type === "expense_request" ? "Reject" : "Don't share")));
  }

  // ---------------------------------------------------------------- tax
  const DEADLINES = [
    ["2026-10-31", "ITR due for FY 2025-26 if your accounts need a tax audit"],
    ["2026-12-15", "Advance tax: 75% of this year's tax, if tax after TDS is ₹10,000 or more"],
    ["2026-12-31", "Last date for a belated FY 2025-26 return"],
    ["2027-03-15", "Advance tax: 100% of this year's tax"],
    ["2027-03-31", "Last day for this year's tax-saving investments and booking gains or losses"],
    ["2027-06-15", "Advance tax: 15% of next year's tax"],
    ["2027-07-31", "ITR due for FY 2026-27 (ITR-1, ITR-2)"],
    ["2027-08-31", "ITR due for freelancers and businesses without audit (ITR-3, ITR-4)"],
  ];
  async function tabTax(main) {
    const t = await api("tax_overview");
    main.replaceChildren(topbar("Tax"));
    const itr = t.itr || {};
    const filed = itr.itr_filed_fy_2025_26;
    main.append(h("div", { class: "grid g-2" },
      h("div", { class: "panel hud stack" }, h("p", { class: "label" }, "Return for FY 2025-26"),
        h("p", { class: `figure sm ${filed ? "good" : "warn"}` }, filed ? "Filed" : "Not filed yet"),
        h("dl", { class: "kv" }, h("dt", {}, "Form"), h("dd", {}, itr.itr_form || "—"), h("dt", {}, "Filed on"), h("dd", {}, itr.itr_filed_on || "—"),
          h("dt", {}, "Outcome"), h("dd", {}, itr.itr_outcome || "—")),
        h("p", { class: "note" }, filed ? "Keep an eye on email from the income-tax department for the 143(1) intimation. Ask Andy in Claude Code with /notice if one arrives." :
          "A belated return can still be filed until 31 Dec 2026, with a late fee.")),
      h("div", { class: "panel hud stack" }, h("p", { class: "label" }, "This year · FY 2026-27"),
        t.comparison ? [h("p", { class: "figure sm" }, `${t.comparison.recommended === "new" ? "New" : "Old"} regime`),
          h("dl", { class: "kv" }, h("dt", {}, "Old regime tax"), h("dd", {}, inr(t.comparison.old)), h("dt", {}, "New regime tax"), h("dd", {}, inr(t.comparison.new)),
            h("dt", {}, "Difference"), h("dd", { class: "iris" }, inr(t.comparison.saving))),
          h("p", { class: "note" }, t.comparison.note)] :
          h("p", { class: "dim" }, "Add your annual gross salary in My Info to see an estimate."))));
    const today = todayISO();
    main.append(h("div", { class: "panel" }, h("p", { class: "label", style: "margin-bottom:10px" }, "Coming up"),
      h("div", { class: "table-wrap" }, h("table", {}, h("tbody", {}, DEADLINES.filter(([d]) => d >= today).slice(0, 6).map(([d, what]) => {
        const days = Math.round((new Date(d + "T00:00:00") - new Date(today + "T00:00:00")) / 864e5);
        return h("tr", {}, h("td", { class: "num" }, new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })),
          h("td", {}, what), h("td", { class: "num" }, h("span", { class: `pill ${days <= 30 ? "warn" : ""}` }, `${days} days`)));
      }))))));
  }

  // ---------------------------------------------------------------- my info
  async function tabInfo(main) {
    const info = await api("get_profile");
    const p = info.profile;
    const again = () => tabInfo(main);
    main.replaceChildren(topbar("My info"));
    const groups = STEPS.filter(st => st.fields);
    const titles = ["About you", "Income", "Monthly commitments", "Safety net", "Taxes", "Goals"];
    groups.forEach((g, i) => {
      const err = errorLine(), save = h("button", { class: "btn sm", type: "button" }, "Save");
      save.addEventListener("click", async () => {
        try { await busy(save, "Saving…", () => api("save_profile", collect(g.fields))); toast("Saved."); state.status = await api("status"); } catch (x) { err.textContent = x.message; }
      });
      main.append(h("div", { class: "panel stack" }, h("div", { class: "panel-head" }, h("p", { class: "label" }, titles[i]), save),
        h("div", { class: "form-grid" }, g.fields.map(f => control(f, p))), err));
    });
    // Budgets
    const inputs = {}, total = money("f-monthly_budget", p.monthly_budget);
    const berr = errorLine(), bsave = h("button", { class: "btn sm", type: "button" }, "Save");
    bsave.addEventListener("click", async () => {
      try {
        const b = {};
        for (const [c, el] of Object.entries(inputs)) b[c] = readMoney(el);
        await api("save_profile", { monthly_budget: readMoney(total) });
        await api("save_budgets", b);
        toast("Budgets saved.");
      } catch (x) { berr.textContent = x.message; }
    });
    main.append(h("div", { class: "panel stack" }, h("div", { class: "panel-head" }, h("p", { class: "label" }, "Monthly budgets"), bsave),
      h("div", { class: "form-grid" }, field("Total", total), BUDGET_CATS.map(c => { inputs[c] = money(`b-${c}`, info.budgets[c]); return field(c, inputs[c]); })), berr));
    // Gmail
    const g = info.gmail;
    const gmailPanel = h("div", { class: "panel hud stack" }, h("div", { class: "panel-head" }, h("p", { class: "label" }, "Gmail · bank, card and UPI alerts"),
      h("span", { class: `pill ${g.connected ? "good" : ""}` }, h("i", { class: "dot" }), g.connected ? "Connected · read-only" : "Not connected")));
    if (g.connected) {
      const disconnect = h("button", { class: "btn danger", type: "button" }, "Disconnect");
      disconnect.addEventListener("click", async () => { try { await api("gmail_disconnect"); toast("Gmail disconnected. The app password was erased from the vault."); again(); } catch (x) { fail(x); } });
      gmailPanel.append(h("dl", { class: "kv" }, h("dt", {}, "Account"), h("dd", {}, g.address), h("dt", {}, "Last sync"), h("dd", {}, g.last_sync || "never")),
        h("div", { class: "row" }, syncButton(again), disconnect),
        h("p", { class: "note" }, "Andy only accepts alerts from known bank and card domains that pass Gmail's DKIM or DMARC check, so a fake “bank” email can't add transactions."));
    } else gmailPanel.append(gmailConnectForm(g, again));
    main.append(gmailPanel);
  }

  // ---------------------------------------------------------------- security
  async function tabSecurity(main) {
    const [info, log] = await Promise.all([api("get_profile"), api("audit_log")]);
    const st = info.settings;
    const again = () => tabSecurity(main);
    main.replaceChildren(topbar("Security", h("button", { class: "btn", type: "button", onclick: lockNow }, icon("lock"), "Lock now")));
    main.append(h("div", { class: "panel hud" }, h("p", { class: "label", style: "margin-bottom:12px" }, "How your vault is protected"),
      h("dl", { class: "kv" },
        h("dt", {}, "Encryption"), h("dd", {}, "AES-256-GCM"),
        h("dt", {}, "Passphrase stretching"), h("dd", {}, "scrypt · 128 MB per guess"),
        h("dt", {}, "Device binding"), h("dd", {}, state.status.dev_mode ? "Dev mode (test only)" : "Windows DPAPI · this PC and account"),
        h("dt", {}, "Stored at"), h("dd", {}, "%LOCALAPPDATA%\\Andy\\vault.andy"),
        h("dt", {}, "Network"), h("dd", {}, "imap.gmail.com only, read-only"),
        h("dt", {}, "Screen capture"), h("dd", {}, "Blocked for other apps"),
        h("dt", {}, "Auto-lock"), h("dd", {}, `${st.auto_lock_minutes} min idle`))));

    // Settings
    const minutes = h("select", { class: "input", id: "s-min" }, [1, 2, 5, 10, 15, 30].map(m => h("option", { value: m, selected: m === st.auto_lock_minutes ? "selected" : null }, `${m} minute${m === 1 ? "" : "s"}`)));
    const threshold = money("s-th", st.approval_passphrase_above);
    const domains = h("input", { class: "input", id: "s-dom", value: (st.extra_bank_domains || []).join(", "), placeholder: "e.g. mybank.co.in" });
    const serr = errorLine(), ssave = h("button", { class: "btn sm", type: "button" }, "Save");
    ssave.addEventListener("click", async () => {
      try { await api("save_settings", { auto_lock_minutes: Number(minutes.value), approval_passphrase_above: readMoney(threshold), extra_bank_domains: domains.value }); toast("Settings saved."); again(); }
      catch (x) { serr.textContent = x.message; }
    });
    main.append(h("div", { class: "panel stack" }, h("div", { class: "panel-head" }, h("p", { class: "label" }, "Rules"), ssave),
      h("div", { class: "form-grid" }, field("Lock after", minutes), field("Ask for passphrase to approve spends above", threshold),
        field("Extra bank email domains", domains, "Only if your bank's alerts aren't being picked up.")), serr));

    // Donna pairing
    const dp = pass("d-pp"), derr = errorLine();
    const donnaPanel = h("div", { class: "panel hud stack" }, h("div", { class: "panel-head" }, h("p", { class: "label" }, "Donna"),
      h("span", { class: `pill ${info.donna.paired ? "good" : ""}` }, h("i", { class: "dot" }), info.donna.paired ? `Paired ${String(info.donna.paired_at || "").replace("T", " ")}` : "Not paired")));
    if (state.pairing) {
      donnaPanel.append(h("p", {}, "Give Donna this pairing key once. It's shown only now."),
        h("div", { class: "mono-block" }, state.pairing.pairing_key),
        h("p", { class: "note" }, "On this PC, set it as ANDY_DONNA_PAIRING in Donna's environment. Donna then sends requests with:"),
        h("div", { class: "mono-block" }, 'python -m andy.donna_client expense --amount 1499 --payee "Cult.fit" --purpose "Monthly gym"'),
        h("button", { class: "btn sm", type: "button", onclick: () => { state.pairing = null; again(); } }, "Done, hide the key"));
    } else {
      const pairBtn = h("button", { class: "btn", type: "button" }, info.donna.paired ? "Issue a new key" : "Pair with Donna");
      pairBtn.addEventListener("click", async () => { try { state.pairing = await api("donna_pair", dp.value); again(); } catch (x) { derr.textContent = x.message; } });
      const unpair = info.donna.paired ? h("button", { class: "btn danger", type: "button" }, "Disconnect Donna") : null;
      if (unpair) unpair.addEventListener("click", async () => { try { await api("donna_unpair", dp.value); toast("Donna disconnected."); again(); } catch (x) { derr.textContent = x.message; } });
      donnaPanel.append(h("p", { class: "dim" }, "Donna talks to Andy through encrypted files on this PC, with no network port. She can propose expenses and ask for summaries. Nothing happens until you approve it."),
        field("Your passphrase", dp), derr, h("div", { class: "row" }, pairBtn, unpair));
    }
    main.append(donnaPanel);

    // Change passphrase
    const o = pass("cp-o"), n1 = pass("cp-n1", "new-password"), n2 = pass("cp-n2", "new-password"), cerr = errorLine();
    const cgo = h("button", { class: "btn sm", type: "button" }, "Change passphrase");
    cgo.addEventListener("click", async () => {
      try { await busy(cgo, "Re-sealing…", () => api("change_passphrase", o.value, n1.value, n2.value)); [o, n1, n2].forEach(x => { x.value = ""; }); toast("Passphrase changed."); }
      catch (x) { cerr.textContent = x.message; }
    });
    main.append(h("div", { class: "panel stack" }, h("p", { class: "label" }, "Change passphrase"),
      h("div", { class: "form-grid" }, field("Current", o), field("New", n1), field("New, again", n2)), cerr, h("div", {}, cgo)));

    // Audit log
    main.append(h("div", { class: "panel" }, h("p", { class: "label", style: "margin-bottom:10px" }, "Activity log"),
      h("div", { class: "table-wrap" }, h("table", { class: "audit" }, h("tbody", {}, log.events.slice(0, 60).map(e =>
        h("tr", {}, h("td", { class: "dim" }, e.ts.replace("T", " ")), h("td", {}, e.event), h("td", { class: "dim" }, e.detail))))))));
  }

  // ---------------------------------------------------------------- start
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (state.status && state.status.unlocked && state.status.onboarded && !document.querySelector(".gate")) renderShell(); }, 350);
  });

  async function start() {
    try { await refreshStatus(); route(); } catch (x) {
      app.replaceChildren(h("div", { class: "gate" }, h("div", { class: "gate-card" }, orb(), h("p", { class: "error" }, x.message))));
    }
  }
  if (window.pywebview && window.pywebview.api && Object.keys(window.pywebview.api).length) start();
  else window.addEventListener("pywebviewready", start, { once: true });
})();

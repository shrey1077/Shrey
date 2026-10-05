'use strict';
// Donna's widget page. Everything from the feed is rendered as text, never as HTML.

(() => {
  const api = window.donna;
  const $ = (id) => document.getElementById(id);
  const clock = () => (window.donnaClock ? window.donnaClock() : new Date());

  if (!api) {
    document.body.textContent = 'Open this through the Donna app (npm start), or preview.html for a demo.';
    return;
  }

  const ICONS = { anchor: '⚓', meal: '🍽', meeting: '📅', event: '📌', buffer: '⏳', reset: '↺', focus: '🎯', break: '☕' };
  const CHECKABLE = new Set(['focus', 'anchor', 'meal', 'event']);
  const MINOR = new Set(['break', 'buffer', 'reset']);
  const NOT_NEXT = new Set(['break', 'reset']);
  const LABEL = { focus: 'Now', meeting: 'Now', break: 'Break', meal: 'Eat', anchor: 'Now', buffer: 'Get ready', event: 'Now' };

  const FACE_FOR = {
    angry: { focus: 'serious', meeting: 'serious', break: 'amused', meal: 'intimidating', anchor: 'neutral', buffer: 'thoughtful', event: 'neutral' },
    classic: { focus: 'serious', meeting: 'serious', break: 'amused', meal: 'happy', anchor: 'neutral', buffer: 'thoughtful', event: 'happy' },
  };

  const LINES = {
    angry: {
      focus: ["Focus. I'm watching the clock so you don't have to.", 'One thing. This thing. Go.', 'Phone face down. I mean it.'],
      meeting: ['Be on time. Be brilliant. In that order.', 'Camera on, notes open. Go.'],
      break: ['Break. Away from the screen. That includes your phone.', 'Water. Stretch. Then back.'],
      meal: ['Food. Now. Not after ‘one more thing’.', "Eat something real. I'm not asking."],
      anchor: ['Do this one properly. Then we talk.'],
      buffer: ['Get ready. Notes open, water poured.'],
      event: ["Don't be late."],
      idle: ['Nothing scheduled. Suspicious.', 'Free time. Use it on purpose.'],
      allDone: ["All done. Fine. I'm impressed. Don't tell anyone."],
      none: ['No plan. Ask me to plan your day.'],
      stale: ["That plan is old. Ask me for today's."],
      done: ['Done. Good. Next.', "Fine. That was good. Don't make me say it twice."],
      skipped: ['Skipped. Fine. The next one counts.'],
      snoozed: ["Five minutes. I'm counting."],
      noted: ['Noted. Go back to what you were doing.'],
    },
    classic: {
      focus: ["Focus time. I'll keep an eye on the clock.", 'Just this one thing for now.'],
      meeting: ["You've got this. Notes open?"],
      break: ['Break time. Step away for a bit.', 'Water and a stretch.'],
      meal: ['Time to eat something good.'],
      anchor: ['Take this one slowly.'],
      buffer: ["A few minutes to get ready."],
      event: ['Enjoy it.'],
      idle: ['Nothing scheduled right now.'],
      allDone: ['Everything done. Lovely work today.'],
      none: ['No plan yet. Ask me to plan your day.'],
      stale: ["That's an old plan. Ask me for today's."],
      done: ['Nicely done.', 'One more off the list.'],
      skipped: ["No problem. On to the next."],
      snoozed: ['Five more minutes.'],
      noted: ["Noted. I'll take it from here."],
    },
  };

  let state = { config: { layout: 'angry', chime: true, mode: 'card' }, feed: null, error: '', discreet: false };
  let marks = {};
  let transient = null;
  let snoozeTimer = null;
  let lastRender = '';
  let audio = null;

  const toMin = (t) => {
    const [h, m] = t.split(':').map(Number);
    return h * 60 + m;
  };
  const nowMin = () => {
    const d = clock();
    return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60;
  };
  const today = () => clock().toLocaleDateString('en-CA');
  const hash = (s) => [...String(s)].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);
  const lines = () => LINES[state.config.layout] || LINES.angry;
  const pick = (key, seed = '') => {
    const set = lines()[key] || lines().idle;
    return set[hash(seed + key) % set.length];
  };

  function left(mins) {
    const s = Math.max(0, Math.round(mins * 60));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return h ? `${h}:${String(m).padStart(2, '0')}` : `${m}:${String(s % 60).padStart(2, '0')}`;
  }

  // ---- marks: done and skipped, kept per day on this machine ----

  const marksKey = () => `donna-marks-${today()}`;
  function loadMarks() {
    try {
      marks = JSON.parse(localStorage.getItem(marksKey()) || '{}');
    } catch {
      marks = {};
    }
  }
  function saveMarks() {
    try {
      localStorage.setItem(marksKey(), JSON.stringify(marks));
    } catch {
      /* storage unavailable: marks last until restart */
    }
  }

  // ---- the plan ----

  const fresh = () => Boolean(state.feed && state.feed.date === today());
  const blocks = () => (fresh() ? state.feed.blocks : []);

  function locate(now) {
    const bs = blocks();
    const current = bs
      .filter((b) => b.kind !== 'reset' && toMin(b.start) <= now && now < toMin(b.end))
      .sort((a, b) => MINOR.has(a.kind) - MINOR.has(b.kind) || toMin(b.start) - toMin(a.start))[0] || null;
    const next = bs.find((b) => !NOT_NEXT.has(b.kind) && toMin(b.start) > now && (!current || b.id !== current.id)) || null;
    const previousEnd = Math.max(0, ...bs.filter((b) => toMin(b.end) <= now).map((b) => toMin(b.end)));
    const remaining = bs.filter((b) => CHECKABLE.has(b.kind) && toMin(b.end) > now && !marks[b.id]);
    return { current, next, previousEnd, allDone: fresh() && bs.length > 0 && remaining.length === 0 && !current };
  }

  function faceFor(where) {
    if (transient && transient.until > Date.now()) return transient.face;
    if (!fresh()) return 'suspicious';
    const map = FACE_FOR[state.config.layout] || FACE_FOR.angry;
    const { current, allDone } = where;
    if (current) {
      if (marks[current.id] === 'skipped') return 'intimidating';
      if (marks[current.id] === 'done') return 'happy';
      return map[current.kind] || 'neutral';
    }
    if (allDone) return 'happy';
    if (state.feed.occasions.length && clock().getHours() < 12) return 'happy';
    return state.feed.mood || 'thoughtful';
  }

  function lineFor(where) {
    if (transient && transient.until > Date.now()) return transient.line;
    if (!state.feed) return pick('none');
    if (!fresh()) return pick('stale');
    const { current, allDone } = where;
    if (current && !marks[current.id]) return pick(current.kind, current.id);
    if (allDone) return pick('allDone', today());
    return state.feed.message || pick('idle', today());
  }

  // ---- rendering ----

  function setText(id, text) {
    const el = $(id);
    if (el.textContent !== text) el.textContent = text;
  }

  function span(cls, text) {
    const s = document.createElement('span');
    s.className = cls;
    s.textContent = text;
    return s;
  }

  function renderNow(where, now) {
    const { current, next, previousEnd } = where;
    const box = $('now');
    const arc = $('arc');
    const full = 276.46;
    let progress = 0;
    box.classList.toggle('idle', !current);
    if (current) {
      const start = toMin(current.start);
      const end = toMin(current.end);
      setText('now-label', LABEL[current.kind] || 'Now');
      setText('now-time', `· ${current.start}–${current.end}`);
      setText('now-title', current.title);
      setText('now-step', current.first_step || '');
      setText('left', left(end - now));
      progress = (now - start) / Math.max(1, end - start);
      $('btn-done').textContent = marks[current.id] === 'done' ? 'Undo' : 'Done';
    } else if (next) {
      const start = toMin(next.start);
      setText('now-label', 'Next');
      setText('now-time', `· at ${next.start}`);
      setText('now-title', next.title);
      setText('now-step', next.first_step || '');
      setText('left', left(start - now));
      progress = (now - previousEnd) / Math.max(1, start - previousEnd);
    } else {
      setText('now-label', fresh() ? 'Today' : 'No plan');
      setText('now-time', fresh() ? '· done' : '');
      setText('now-title', fresh() ? 'Nothing left on the plan' : 'Ask Donna to plan your day');
      const hint = !state.config.hasFolder ? "Choose the plan folder in settings (⚙)." : state.error || (state.feed ? `Last plan: ${state.feed.date}` : '');
      setText('now-step', fresh() ? '' : hint);
      setText('left', '—');
      progress = fresh() ? 1 : 0;
    }
    arc.style.strokeDashoffset = String(full * (1 - Math.min(1, Math.max(0, progress))));

    const after = current ? next : null;
    const nextEl = $('next');
    nextEl.replaceChildren();
    if (after) {
      const b = document.createElement('b');
      b.textContent = `Next · ${after.start}`;
      nextEl.append(b, document.createTextNode(`  ${after.title}`));
    }

    setText('mini-title', current ? current.title : next ? next.title : fresh() ? 'All done' : 'No plan yet');
    setText('mini-meta', current ? `until ${current.end} · ${left(toMin(current.end) - now)} left`
      : next ? `next at ${next.start} · in ${left(toMin(next.start) - now)}` : '');
  }

  function renderTimeline(now, current) {
    const ol = $('timeline');
    ol.replaceChildren();
    let focusEl = null;
    for (const b of blocks()) {
      if (b.kind === 'reset') continue;
      const li = document.createElement('li');
      const classes = [];
      if (toMin(b.end) <= now) classes.push('past');
      if (current && current.id === b.id) classes.push('current');
      if (marks[b.id]) classes.push(marks[b.id]);
      if (MINOR.has(b.kind)) classes.push('minor');
      if (CHECKABLE.has(b.kind)) classes.push('checkable');
      li.className = classes.join(' ');
      const status = marks[b.id] === 'done' ? '✓' : marks[b.id] === 'skipped' ? '↷' : '';
      li.append(span('t', b.start), span('i', ICONS[b.kind] || '•'), span('title', b.title), span('s', status));
      if (CHECKABLE.has(b.kind)) li.addEventListener('click', () => mark(b, marks[b.id] === 'done' ? 'undo' : 'done'));
      ol.append(li);
      if (!focusEl && (classes.includes('current') || !classes.includes('past'))) focusEl = li;
    }
    // Scroll only the list (never the window) so the current item sits near the top.
    if (focusEl) ol.scrollTop += focusEl.getBoundingClientRect().top - ol.getBoundingClientRect().top - 4;
  }

  function renderExtras() {
    const box = $('extras');
    box.replaceChildren();
    if (!fresh()) return;
    const f = state.feed;
    const add = (k, text) => {
      const p = document.createElement('p');
      p.append(span('k', k), document.createTextNode(text));
      box.append(p);
    };
    for (const o of f.occasions.slice(0, 2)) add('Today', `🎂 ${o.who}${o.what ? ` (${o.what})` : ''}${o.action ? ` · ${o.action}` : ''}`);
    if (f.outfit && f.outfit.summary) add('Wear', f.outfit.summary);
    if (f.events[0]) add('Tonight', `${f.events[0].title}${f.events[0].when ? ` · ${f.events[0].when}` : ''}`);
    if (f.wins[0]) add('Win', f.wins[0]);
  }

  function tick(force = false) {
    const now = nowMin();
    const where = locate(now);
    const face = faceFor(where);
    const faceEl = $('face-img');
    if (faceEl.dataset.face !== face) Faces.paint(faceEl, face);
    setText('line', lineFor(where));
    renderNow(where, now);
    const key = `${today()}|${where.current ? where.current.id : ''}|${Math.floor(now)}|${JSON.stringify(marks)}|${state.feed ? state.feed.generated_at : ''}`;
    if (force || key !== lastRender) {
      lastRender = key;
      renderTimeline(now, where.current);
      renderExtras();
    }
  }

  // ---- actions ----

  function say(face, line, seconds = 8) {
    transient = { face, line, until: Date.now() + seconds * 1000 };
    Faces.paint($('face-img'), face);
    tick(true);
  }

  function mark(block, action) {
    if (action === 'undo') delete marks[block.id];
    else marks[block.id] = action === 'skip' ? 'skipped' : 'done';
    saveMarks();
    api.log(block.id, action);
    if (action === 'done') {
      chime();
      say('happy', pick('done', block.id + Date.now()));
    } else if (action === 'skip') {
      say('intimidating', pick('skipped'));
    } else {
      tick(true);
    }
  }

  function currentBlock() {
    return locate(nowMin()).current;
  }

  $('btn-done').addEventListener('click', () => {
    const b = currentBlock();
    if (b) mark(b, marks[b.id] === 'done' ? 'undo' : 'done');
  });

  $('btn-skip').addEventListener('click', () => {
    const b = currentBlock();
    if (b) mark(b, 'skip');
  });

  $('btn-snooze').addEventListener('click', () => {
    const b = currentBlock();
    if (!b) return;
    api.log(b.id, 'snooze');
    clearTimeout(snoozeTimer);
    snoozeTimer = setTimeout(() => api.notify('Donna', `Back to it: ${b.title}`), 5 * 60 * 1000);
    say('suspicious', pick('snoozed'));
  });

  $('capture').addEventListener('submit', async (e) => {
    e.preventDefault();
    const input = $('capture-text');
    const text = input.value.trim();
    if (!text) return;
    const ok = await api.capture(text);
    if (ok) {
      input.value = '';
      $('capture').classList.add('sent');
      setTimeout(() => $('capture').classList.remove('sent'), 1500);
      say('neutral', pick('noted'), 5);
    } else {
      say('suspicious', 'Choose the plan folder in settings first.', 6);
    }
  });

  function chime() {
    if (!state.config.chime) return;
    try {
      audio = audio || new AudioContext();
      const t = audio.currentTime;
      [659.25, 987.77].forEach((freq, i) => {
        const osc = audio.createOscillator();
        const gain = audio.createGain();
        const s = t + i * 0.18;
        osc.type = 'sine';
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0, s);
        gain.gain.linearRampToValueAtTime(0.16, s + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, s + 0.9);
        osc.connect(gain).connect(audio.destination);
        osc.start(s);
        osc.stop(s + 1);
      });
    } catch {
      /* no audio device */
    }
  }

  function nudged(n) {
    const card = $('card');
    card.classList.remove('nudge');
    void card.offsetWidth;
    card.classList.add('nudge');
    chime();
    say(n.kind === 'meal' && state.config.layout === 'angry' ? 'intimidating' : 'surprised', n.title, 12);
  }

  // ---- modes ----

  function setDiscreet(on) {
    state.discreet = Boolean(on);
    document.body.classList.toggle('discreet', state.discreet);
  }

  $('btn-discreet').addEventListener('click', () => {
    setDiscreet(!state.discreet);
    api.set('discreet', state.discreet);
  });

  $('face').addEventListener('click', async () => {
    const mode = document.body.dataset.mode === 'mini' ? 'card' : 'mini';
    state.config = await api.set('mode', mode);
    document.body.dataset.mode = mode;
    if (mode === 'mini') $('settings').hidden = true;
    tick(true);
  });

  $('btn-quit').addEventListener('click', () => api.quit());

  // ---- settings ----

  function renderSettings() {
    const c = state.config;
    setText('set-folder', c.hasFolder ? 'Chosen ✓' : 'Not chosen: pick Donna/widget in your synced Google Drive');
    setText('set-sheet', c.hasSheet ? 'Chosen ✓' : 'Not chosen: pick the character sheet image');
    for (const b of document.querySelectorAll('.seg button')) b.setAttribute('aria-checked', String(b.dataset.layout === c.layout));
    $('set-top').checked = Boolean(c.alwaysOnTop);
    $('set-login').checked = Boolean(c.startAtLogin);
    $('set-chime').checked = Boolean(c.chime);
    setText('faces-how', c.hasSheet ? (Faces.detected() ? 'found on your sheet' : 'from standard positions') : '');
    const ol = $('faces');
    ol.replaceChildren();
    const labels = Faces.LABELS[c.layout] || Faces.LABELS.angry;
    Faces.NAMES.forEach((name, i) => {
      const li = document.createElement('li');
      const img = span('face-img', '');
      li.append(img, span('', labels[i]));
      ol.append(li);
      requestAnimationFrame(() => Faces.paint(img, name));
    });
  }

  $('btn-settings').addEventListener('click', () => {
    $('settings').hidden = false;
    renderSettings();
  });
  $('btn-close-settings').addEventListener('click', () => { $('settings').hidden = true; });

  $('btn-folder').addEventListener('click', async () => {
    state.config = await api.pickFolder();
    renderSettings();
  });

  $('btn-sheet').addEventListener('click', async () => {
    const r = await api.pickSheet();
    state.config = r.config;
    await Faces.load(r.sheet, state.config.layout);
    Faces.paint($('face-img'), faceFor(locate(nowMin())));
    renderSettings();
  });

  for (const b of document.querySelectorAll('.seg button')) {
    b.addEventListener('click', async () => {
      state.config = await api.set('layout', b.dataset.layout);
      const s = await api.state();
      await Faces.load(s.sheet, state.config.layout);
      $('face-img').dataset.face = '';
      renderSettings();
      tick(true);
    });
  }

  for (const [id, key] of [['set-top', 'alwaysOnTop'], ['set-login', 'startAtLogin'], ['set-chime', 'chime']]) {
    $(id).addEventListener('change', async (e) => {
      state.config = await api.set(key, e.target.checked);
    });
  }

  // ---- start ----

  api.on('feed', ({ feed, error }) => {
    state.feed = feed;
    state.error = error;
    loadMarks();
    tick(true);
  });
  api.on('nudge', nudged);
  api.on('discreet', setDiscreet);

  (async () => {
    const s = await api.state();
    state = { ...state, ...s };
    document.body.dataset.mode = s.config.mode;
    setDiscreet(s.discreet);
    loadMarks();
    await Faces.load(s.sheet, s.config.layout);
    tick(true);
    setInterval(tick, 1000);
    const params = new URLSearchParams(location.search);
    if (params.get('settings') === '1') $('btn-settings').click();
  })();
})();

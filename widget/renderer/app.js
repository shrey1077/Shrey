'use strict';
// Donna's widget page. Everything from the plan or the chat is rendered as text, never as HTML.

(() => {
  const api = window.donna;
  const ROOT = window.DONNA_HOST || document.body; // the preview page hosts the widget in an element
  const $ = (id) => document.getElementById(id);
  const clock = () => (window.donnaClock ? window.donnaClock() : new Date());

  if (!api) {
    ROOT.textContent = 'Open this through the Donna app (npm start).';
    return;
  }

  const ICONS = { anchor: '⚓', meal: '🍽', meeting: '📅', event: '📌', buffer: '⏳', reset: '↺', focus: '🎯', break: '☕' };
  const CHECKABLE = new Set(['focus', 'anchor', 'meal', 'event']);
  const MINOR = new Set(['break', 'buffer', 'reset']);
  const NOT_NEXT = new Set(['break', 'reset']);
  const TRACKED = new Set(['focus', 'meeting', 'meal', 'anchor', 'event']); // lateness counts for these
  const LATE_AFTER = 3; // minutes after the start before it counts as late
  const LABEL = { focus: 'Now', meeting: 'Now', break: 'Break', meal: 'Eat', anchor: 'Now', buffer: 'Get ready', event: 'Now' };
  const LATE_KEY = { focus: 'lateFocus', meeting: 'lateMeeting', meal: 'lateMeal', anchor: 'lateAnchor', event: 'lateAnchor' };
  const SCENE_LABEL = {
    focus: 'At work', call: 'On a call', reading: 'Reviewing', coffee: 'Coffee break', lunch: 'Lunch', morning: 'Morning',
    ready: 'Getting ready', commute: 'Heading out', exercise: 'Exercise', winddown: 'Winding down', event: 'Night out',
    celebrate: 'Celebrating', chill: 'Chilling',
  };
  // Her mood in the circle: the word, and the colour family of the ring.
  const MOOD = {
    normal: ['Composed', 'calm'], serious: ['Serious', 'calm'], thoughtful: ['Thinking', 'calm'],
    suspicious: ['Suspicious', 'calm'], surprised: ['Surprised', 'calm'], cool: ['Cool', 'calm'],
    happy: ['Pleased', 'joy'], laughing: ['Laughing', 'joy'], adoring: ['Enchanted', 'joy'],
    relaxed: ['Relaxed', 'joy'], blissful: ['Blissful', 'joy'], amused: ['Amused', 'playful'],
    playful: ['Playful', 'playful'], angry: ['Angry', 'angry'], furious: ['Furious', 'angry'],
    cooling: ['Cooling down', 'sad'], sad: ['Sad', 'sad'], crying: ['Crying', 'sad'], sobbing: ['Sobbing', 'sad'],
  };
  const SLOT_OPTIONS = ['body.normal', 'body.happy', 'body.amused', 'body.angry', 'body.serious', 'body.thoughtful', 'bust',
    'face.normal', 'face.happy', 'face.amused', 'face.angry', 'face.serious', 'face.thoughtful', 'face.surprised',
    'scene.morning', 'scene.focus', 'scene.call', 'scene.coffee', 'scene.lunch', 'scene.exercise', 'scene.winddown', 'scene.event'];

  let state = { config: { temperament: 'earned', dials: { ...Voice.DEFAULT_DIALS }, figure: 'full', chime: true, mode: 'card', chat: {} }, feed: null, error: '', discreet: false };
  let marks = {};
  let transient = null; // { emotion, line, until }
  let snoozeTimer = null;
  let lastRender = '';
  let audio = null;
  let hearSeed = 0;

  // ---- time ----

  const toMin = (t) => {
    const [h, m] = t.split(':').map(Number);
    return h * 60 + m;
  };
  const nowMin = () => {
    const d = clock();
    return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60;
  };
  const today = () => clock().toLocaleDateString('en-CA');
  function left(mins) {
    const s = Math.max(0, Math.round(mins * 60));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return h ? `${h}:${String(m).padStart(2, '0')}` : `${m}:${String(s % 60).padStart(2, '0')}`;
  }

  // ---- storage on this machine (marks per day, the chat) ----

  const store = {
    get(key, fallback) {
      try {
        const v = localStorage.getItem(key);
        return v ? JSON.parse(v) : fallback;
      } catch {
        return fallback;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, JSON.stringify(value));
      } catch {
        /* storage unavailable: keeps until restart */
      }
    },
  };
  const loadMarks = () => { marks = store.get(`donna-marks-${today()}`, {}); };
  const saveMarks = () => store.set(`donna-marks-${today()}`, marks);

  // ---- the plan ----

  const fresh = () => Boolean(state.feed && state.feed.date === today());
  const blocks = () => (fresh() ? state.feed.blocks : []);
  const finished = (id) => marks[id] === 'done' || marks[id] === 'skipped';
  const doneToday = () => Object.values(marks).filter((m) => m === 'done').length;

  function lateBy(b, now) {
    if (!b || !TRACKED.has(b.kind) || marks[b.id]) return 0;
    const n = Math.floor(now - toMin(b.start));
    return n >= LATE_AFTER ? n : 0;
  }

  function locate(now) {
    const bs = blocks();
    const current = bs
      .filter((b) => b.kind !== 'reset' && toMin(b.start) <= now && now < toMin(b.end))
      .sort((a, b) => MINOR.has(a.kind) - MINOR.has(b.kind) || toMin(b.start) - toMin(a.start))[0] || null;
    const next = bs.find((b) => !NOT_NEXT.has(b.kind) && toMin(b.start) > now && (!current || b.id !== current.id)) || null;
    const previousEnd = Math.max(0, ...bs.filter((b) => toMin(b.end) <= now).map((b) => toMin(b.end)));
    const remaining = bs.filter((b) => CHECKABLE.has(b.kind) && toMin(b.end) > now && !finished(b.id));
    return { now, current, next, previousEnd, allDone: fresh() && bs.length > 0 && remaining.length === 0 && !current };
  }

  // What is happening, in Voice's terms.
  function situation(where) {
    const { current, allDone, now } = where;
    if (!state.feed) return { key: 'none', emotion: 'thoughtful' };
    if (!fresh()) return { key: 'stale', emotion: 'suspicious' };
    if (current) {
      const n = lateBy(current, now);
      if (n) return { key: LATE_KEY[current.kind] || 'lateAnchor', n, block: current, late: true };
      if (marks[current.id] === 'started-ontime') return { key: 'onTime', block: current };
      if (marks[current.id] === 'done') return { key: 'done', block: current };
      if (current.kind === 'break' && doneToday() > 0) return { key: 'earnedBreak', block: current };
      return { key: current.kind, block: current };
    }
    if (allDone) return { key: 'allDone' };
    return { key: 'idle' };
  }

  const voiceOpts = (seed, n) => ({ dials: state.config.dials, temperament: state.config.temperament, seed, n });

  // The emotion to show for a line Donna says, with intensity from the dials.
  function emotionFor(key, said, n = 0) {
    const d = Voice.clampDials(state.config.dials);
    const tone = Voice.TONE[key] || 'neutral';
    let e = said.face;
    if (said.trait === 'anger' && n >= 15 && d.anger >= 8) e = 'furious';
    if (said.trait === 'sadness') e = d.sadness >= 8 ? (n >= 30 && d.sadness >= 10 ? 'sobbing' : 'crying') : 'thoughtful';
    if (key === 'allDone' && said.trait === 'happiness') e = d.happiness >= 9 ? 'adoring' : 'laughing';
    if (tone === 'good' && said.trait === 'humour') e = 'playful';
    if (key === 'lateStart') e = 'cooling';
    return e;
  }

  // ---- what she shows ----

  // The picture standing in the corner. Full body follows her mood; Scenes shows what she is doing
  // when things are calm and her mood when they aren't.
  function pictureFor(sit, emotion, strong) {
    const mode = state.config.figure;
    const seed = `${today()}|${sit.block ? sit.block.id : sit.key}`;
    const body = () => Art.find('body', emotion, seed);
    const bust = () => {
      const b = Art.pick('bust', seed);
      return b && { ...b, slot: 'bust' };
    };
    if (mode === 'bust') return bust() || body();
    if (mode === 'scenes' && !strong && sit.block) {
      const scene = Manifest.sceneFor(sit.block);
      const item = scene && Art.pick(`scene.${scene}`, seed);
      if (item) return { ...item, slot: `scene.${scene}` };
    }
    return body() || bust();
  }

  // As tall as the corner allows, feet on the floor; small pieces are enlarged at most twice.
  function fitFigure() {
    const img = $('figure-img');
    const stage = $('stage');
    const framed = stage.classList.contains('framed');
    const w = stage.clientWidth - (framed ? 0 : 12);
    const h = stage.clientHeight - (framed ? 0 : 18);
    if (!img.naturalWidth || w <= 0 || h <= 0) return;
    const k = Math.min(2, w / img.naturalWidth, h / img.naturalHeight);
    img.style.width = `${Math.round(img.naturalWidth * k)}px`;
    img.style.height = `${Math.round(img.naturalHeight * k)}px`;
  }
  $('figure-img').addEventListener('load', fitFigure);

  function showFigure(sit, emotion, strong) {
    const item = pictureFor(sit, emotion, strong);
    const img = $('figure-img');
    $('stage').classList.toggle('has-art', Boolean(item));
    if (item && img.dataset.url !== item.url) {
      img.dataset.url = item.url;
      img.src = item.url;
      $('stage').classList.toggle('framed', !item.cutout);
    } else if (!item && img.dataset.url) {
      img.removeAttribute('src');
      img.dataset.url = '';
    }
    fitFigure(); // the corner changes size with the slim bar and Off
    const [word, tone] = MOOD[emotion] || MOOD.normal;
    const mood = $('mood');
    mood.dataset.tone = tone;
    mood.setAttribute('aria-label', `Donna's mood: ${word}`);
    setText('mood-word', word);
    Art.paintFace($('mood-img'), emotion, today());
    Art.paintFace($('face-img'), emotion, today());
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
    const full = 276.46;
    let progress = 0;
    $('now').classList.toggle('idle', !current);
    if (current) {
      const start = toMin(current.start);
      const end = toMin(current.end);
      setText('now-label', LABEL[current.kind] || 'Now');
      setText('now-time', `· ${current.start}–${current.end}`);
      setText('now-title', current.title);
      setText('now-step', current.first_step || '');
      setText('left', left(end - now));
      progress = (now - start) / Math.max(1, end - start);
      const waiting = TRACKED.has(current.kind) && !marks[current.id];
      $('btn-start').hidden = !waiting;
      $('btn-done').hidden = waiting;
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
      const hint = !state.config.hasFolder ? 'Choose the plan folder in Settings.' : state.error || (state.feed ? `Last plan: ${state.feed.date}` : '');
      setText('now-step', fresh() ? '' : hint);
      setText('left', '—');
      progress = fresh() ? 1 : 0;
    }
    $('arc').style.strokeDashoffset = String(full * (1 - Math.min(1, Math.max(0, progress))));

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
      const status = { done: '✓', skipped: '↷', started: '▸', 'started-ontime': '▸' }[marks[b.id]] || '';
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
    for (const o of f.occasions.slice(0, 1)) add('Today', `🎂 ${o.who}${o.what ? ` (${o.what})` : ''}${o.action ? ` · ${o.action}` : ''}`);
    if (f.outfit && f.outfit.summary) add('Wear', f.outfit.summary);
    if (f.events[0]) add('Tonight', `${f.events[0].title}${f.events[0].when ? ` · ${f.events[0].when}` : ''}`);
  }

  function tick(force = false) {
    const now = nowMin();
    const where = locate(now);
    const sit = situation(where);
    let line;
    let emotion;
    const active = transient && transient.until > Date.now();
    if (active) {
      ({ line, emotion } = transient);
    } else {
      const said = Voice.line(sit.key, voiceOpts(`${today()}|${sit.block ? sit.block.id : ''}`, sit.n));
      emotion = sit.emotion || emotionFor(sit.key, said, sit.n || 0);
      line = sit.key === 'idle' && state.feed && state.feed.message ? state.feed.message : said.text;
    }
    setText('line', line);
    showFigure(sit, emotion, active || sit.late || ['onTime', 'done', 'allDone'].includes(sit.key));
    renderNow(where, now);
    const key = `${today()}|${where.current ? where.current.id : ''}|${Math.floor(now)}|${JSON.stringify(marks)}|${state.feed ? state.feed.generated_at : ''}`;
    if (force || key !== lastRender) {
      lastRender = key;
      renderTimeline(now, where.current);
      renderExtras();
      mergeReplies();
    }
  }

  // ---- actions ----

  function say(key, opts = {}) {
    const said = Voice.line(key, voiceOpts(`${Date.now()}`, opts.n || 0));
    transient = {
      line: opts.line || said.text,
      emotion: opts.emotion || emotionFor(key, said, opts.n || 0),
      until: Date.now() + (opts.seconds || 9) * 1000,
    };
    tick(true);
  }

  function mark(block, action) {
    if (action === 'undo') delete marks[block.id];
    else marks[block.id] = action === 'skip' ? 'skipped' : 'done';
    saveMarks();
    api.log(block.id, action);
    if (action === 'done') {
      chime();
      say('done');
    } else if (action === 'skip') {
      say('skip');
    } else {
      tick(true);
    }
  }

  const currentBlock = () => locate(nowMin()).current;

  $('btn-start').addEventListener('click', () => {
    const b = currentBlock();
    if (!b) return;
    const late = Math.floor(nowMin() - toMin(b.start));
    const onTime = late < LATE_AFTER;
    marks[b.id] = onTime ? 'started-ontime' : 'started';
    saveMarks();
    api.log(b.id, 'start');
    if (onTime) {
      chime();
      say('onTime');
    } else {
      say('lateStart', { n: late });
    }
  });

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
    say('snooze', { n: Math.max(0, Math.floor(nowMin() - toMin(b.start))) });
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
    say('idle', { line: n.title, emotion: n.kind === 'meal' ? 'angry' : 'surprised', seconds: 12 });
  }

  // ---- chat ----

  let messages = store.get('donna-chat', []);
  const seenReplies = new Set(store.get('donna-chat-seen', []));

  function saveChat() {
    messages = messages.slice(-80);
    store.set('donna-chat', messages.filter((m) => !m.typing));
    store.set('donna-chat-seen', [...seenReplies].slice(-100));
  }

  function renderChat() {
    const ol = $('messages');
    ol.replaceChildren(...messages.slice(-40).map((m) => {
      const li = document.createElement('li');
      li.className = `msg ${m.who}${m.typing ? ' typing' : ''}`;
      li.textContent = m.text;
      return li;
    }));
    ol.scrollTop = ol.scrollHeight;
  }

  function addMessage(who, text) {
    messages.push({ who, text, at: new Date().toISOString() });
    saveChat();
    renderChat();
  }

  function mergeReplies() {
    if (!state.feed || !state.feed.replies) return;
    let added = false;
    for (const r of state.feed.replies) {
      const key = `${r.at}|${r.text.slice(0, 60)}`;
      if (seenReplies.has(key)) continue;
      seenReplies.add(key);
      messages.push({ who: 'donna', text: r.text, at: r.at });
      added = true;
    }
    if (added) {
      saveChat();
      renderChat();
    }
  }

  function chatNote() {
    const note = (state.config.chat && state.config.chat.note) || '';
    setText('chat-note', note);
    setText('set-chat-note', note);
  }

  const textarea = $('chat-text');
  textarea.addEventListener('input', () => {
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(72, textarea.scrollHeight)}px`;
  });
  textarea.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      $('composer').requestSubmit();
    }
  });

  let sending = false;
  $('composer').addEventListener('submit', async (e) => {
    e.preventDefault();
    const text = textarea.value.trim();
    if (!text || sending) return;
    sending = true;
    $('composer').classList.add('busy');
    textarea.value = '';
    textarea.style.height = 'auto';
    addMessage('me', text);
    if (state.config.chat && state.config.chat.live) {
      messages.push({ who: 'donna', text: '', typing: true });
      renderChat();
    }
    let res;
    try {
      res = await api.chatSend(text);
    } catch (err) {
      res = { error: String(err.message || err) };
    }
    messages = messages.filter((m) => !m.typing);
    if (res.reply) {
      addMessage('donna', res.reply);
      say('idle', { line: res.reply.length > 90 ? `${res.reply.slice(0, 87)}…` : res.reply, emotion: 'normal', seconds: 6 });
    } else if (res.via === 'inbox') {
      const ack = Voice.line('chatAck', voiceOpts(text));
      addMessage('donna', ack.text);
      say('chatAck', { line: ack.text, emotion: ack.face, seconds: 5 });
    } else {
      addMessage('sys', res.error || 'That did not go through.');
    }
    sending = false;
    $('composer').classList.remove('busy');
  });

  // ---- modes and tabs ----

  function setDiscreet(on) {
    state.discreet = Boolean(on);
    ROOT.classList.toggle('discreet', state.discreet);
  }

  $('btn-discreet').addEventListener('click', () => {
    setDiscreet(!state.discreet);
    api.set('discreet', state.discreet);
  });

  async function setMode(mode) {
    state.config = await api.set('mode', mode);
    ROOT.dataset.mode = mode;
    tick(true);
  }

  $('btn-mini').addEventListener('click', () => setMode('mini'));
  $('face').addEventListener('click', () => setMode('card'));
  $('btn-quit').addEventListener('click', () => api.quit());

  function showTab(name) {
    $('tab-day').setAttribute('aria-selected', String(name === 'day'));
    $('tab-settings').setAttribute('aria-selected', String(name === 'settings'));
    $('view-day').hidden = name !== 'day';
    $('view-settings').hidden = name !== 'settings';
    if (name === 'settings') renderSettings();
  }
  $('tab-day').addEventListener('click', () => showTab('day'));
  $('tab-settings').addEventListener('click', () => showTab('settings'));

  // ---- settings ----

  function segSync(id, value) {
    for (const b of $(id).querySelectorAll('button')) b.setAttribute('aria-checked', String(b.dataset.value === value));
  }

  function hear() {
    setText('hear-late', Voice.line('lateFocus', voiceOpts(`hear${hearSeed}`, 12)).text);
    setText('hear-good', Voice.line('done', voiceOpts(`hear${hearSeed}`)).text);
  }

  function renderDials() {
    const box = $('dials');
    if (!box.childElementCount) {
      for (const k of Voice.DIALS) {
        const wrap = document.createElement('div');
        wrap.className = 'dial';
        const label = document.createElement('label');
        label.htmlFor = `dial-${k}`;
        const out = document.createElement('output');
        out.id = `dial-${k}-out`;
        label.append(document.createTextNode(k[0].toUpperCase() + k.slice(1)), out);
        const input = document.createElement('input');
        input.type = 'range';
        input.min = '0';
        input.max = '10';
        input.step = '1';
        input.id = `dial-${k}`;
        const help = document.createElement('p');
        help.textContent = Voice.DIAL_HELP[k];
        input.addEventListener('input', () => {
          state.config.dials = { ...state.config.dials, [k]: Number(input.value) };
          out.textContent = input.value;
          hear();
        });
        input.addEventListener('change', async () => {
          state.config = await api.set('dials', state.config.dials);
          tick(true);
        });
        wrap.append(label, input, help);
        box.append(wrap);
      }
    }
    const d = Voice.clampDials(state.config.dials);
    for (const k of Voice.DIALS) {
      $(`dial-${k}`).value = String(d[k]);
      $(`dial-${k}-out`).textContent = String(d[k]);
    }
  }

  const thumbs = {};
  async function thumb(name, el) {
    if (!(name in thumbs)) {
      try {
        const url = await api.artImage(name);
        const img = new Image();
        await new Promise((ok, bad) => {
          img.onload = ok;
          img.onerror = bad;
          img.src = url;
        });
        const c = document.createElement('canvas');
        c.width = 88;
        c.height = Math.max(1, Math.round((88 * img.naturalHeight) / img.naturalWidth));
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
        thumbs[name] = c.toDataURL('image/jpeg', 0.8);
      } catch {
        thumbs[name] = '';
      }
    }
    if (thumbs[name]) el.style.backgroundImage = `url("${thumbs[name]}")`;
  }

  function slotLabel(slot) {
    if (slot === 'bust') return 'Half bust';
    const [kind, name] = slot.split('.');
    const nice = kind === 'scene' && SCENE_LABEL[name] ? SCENE_LABEL[name] : name[0].toUpperCase() + name.slice(1);
    return kind === 'body' ? `${nice} · full` : kind === 'face' ? `${nice} · close-up` : nice;
  }

  function typeSelect(file, sheetTypes) {
    const sel = document.createElement('select');
    sel.setAttribute('aria-label', `What is ${file.name}?`);
    const opt = (value, text, parent = sel) => {
      const o = document.createElement('option');
      o.value = value;
      o.textContent = text;
      parent.append(o);
    };
    opt('', 'Not sorted yet');
    const sheets = document.createElement('optgroup');
    sheets.label = 'A sheet to cut';
    for (const [k, label] of Object.entries(sheetTypes)) opt(k, label, sheets);
    sel.append(sheets);
    const singles = document.createElement('optgroup');
    singles.label = 'One picture, used as';
    for (const s of SLOT_OPTIONS) opt(`slot:${s}`, slotLabel(s), singles);
    sel.append(singles);
    opt('ignore', 'Ignore');
    sel.value = file.type || '';
    sel.addEventListener('change', () => api.set('sheetType', { name: file.name, type: sel.value }));
    return sel;
  }

  let art = { folder: '', files: [], cuts: 0, sheetTypes: {} };

  function renderArt() {
    setText('set-art', art.folder ? `${art.folder} · ${art.files.length} pictures` : 'Not chosen');
    const ol = $('files');
    ol.replaceChildren();
    for (const f of art.files) {
      const li = document.createElement('li');
      const t = span('thumb', '');
      li.append(t, span('name', f.name), typeSelect(f, art.sheetTypes));
      ol.append(li);
      thumb(f.name, t);
    }
    setText('cut-status', Art.count() ? `${Art.count()} pictures in ${Art.list().length} emotions and scenes.` : 'Nothing cut yet.');
    const slots = $('slots');
    slots.replaceChildren();
    for (const slot of Art.list()) {
      const li = document.createElement('li');
      const img = document.createElement('img');
      img.alt = '';
      img.src = Art.pick(slot).url;
      li.append(img, span('', slotLabel(slot)));
      slots.append(li);
    }
  }

  function renderSettings() {
    const c = state.config;
    segSync('set-temper', c.temperament);
    segSync('set-figure', c.figure);
    segSync('set-chat-mode', (c.chat && c.chat.mode) || 'auto');
    renderDials();
    hear();
    setText('set-folder', c.hasFolder ? 'Chosen ✓' : 'Not chosen: pick Donna/widget in your synced Google Drive');
    setText('set-claude', c.chat && c.chat.claude ? `Found: ${c.chat.claude}` : 'Not found');
    setText('set-repo', c.chat && c.chat.repo ? `Found: ${c.chat.repo}` : 'Not found');
    $('set-top').checked = Boolean(c.alwaysOnTop);
    $('set-login').checked = Boolean(c.startAtLogin);
    $('set-chime').checked = Boolean(c.chime);
    chatNote();
    api.artState().then((a) => {
      art = a;
      renderArt();
    });
  }

  function onSeg(id, key, after) {
    for (const b of $(id).querySelectorAll('button')) {
      b.addEventListener('click', async () => {
        state.config = await api.set(key, b.dataset.value);
        segSync(id, b.dataset.value);
        if (after) after(b.dataset.value);
        tick(true);
      });
    }
  }
  onSeg('set-temper', 'temperament', hear);
  onSeg('set-figure', 'figure', (v) => { ROOT.dataset.figure = v; });
  onSeg('set-chat-mode', 'chatMode', chatNote);

  $('btn-hear').addEventListener('click', () => {
    hearSeed += 1;
    hear();
  });

  $('btn-art').addEventListener('click', async () => {
    art = await api.pickArt();
    state.config = (await api.state()).config;
    renderArt();
  });

  $('btn-cut').addEventListener('click', async () => {
    art = await api.artState();
    const todo = art.files.filter((f) => f.type && f.type !== 'ignore');
    if (!todo.length) {
      setText('cut-status', 'Say what each picture is first.');
      return;
    }
    const pieces = [];
    for (const [i, f] of todo.entries()) {
      setText('cut-status', `Cutting ${i + 1} of ${todo.length}: ${f.name}`);
      try {
        const url = await api.artImage(f.name);
        if (f.type.startsWith('slot:')) pieces.push(await Art.single(url, f.type.slice(5)));
        else pieces.push(...(await Art.cutSheet(url, f.type)));
      } catch {
        setText('cut-status', `Couldn't read ${f.name}; skipped it.`);
      }
    }
    const saved = await api.artSave(pieces);
    Art.reset();
    for (const p of pieces) Art.add(p.slot, p);
    renderArt();
    setText('cut-status', `Cut ${saved} pictures into ${Art.list().length} emotions and scenes, saved in donna-cut.`);
    tick(true);
  });

  const cleanError = (err) => String(err.message || err).replace(/^Error invoking remote method '[^']+': (Error: )?/, '');

  $('btn-folder').addEventListener('click', async () => {
    state.config = await api.pickFolder();
    renderSettings();
  });
  $('btn-repo').addEventListener('click', async () => {
    try {
      state.config = await api.pickRepo();
      renderSettings();
    } catch (err) {
      setText('set-repo', cleanError(err));
    }
  });
  $('btn-claude').addEventListener('click', async () => {
    try {
      state.config = await api.pickClaude();
      renderSettings();
    } catch (err) {
      setText('set-claude', cleanError(err));
    }
  });
  $('btn-new-chat').addEventListener('click', async () => {
    await api.chatReset();
    addMessage('sys', 'New conversation');
  });

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
    ROOT.dataset.mode = s.config.mode;
    ROOT.dataset.figure = s.config.figure;
    setDiscreet(s.discreet);
    loadMarks();
    chatNote();
    renderChat();
    const cuts = await api.artCuts();
    for (const c of cuts) Art.add(c.slot, c);
    if (!cuts.length && s.legacySheet) {
      for (const p of await Art.cutSheet(s.legacySheet, 'character')) Art.add(p.slot, p);
    }
    tick(true);
    setInterval(tick, 1000);
    if (new URLSearchParams(location.search).get('settings') === '1') showTab('settings');
  })();
})();

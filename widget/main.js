'use strict';
// Donna's desktop widget: her figure, today's plan from a synced folder, nudges on time, and a chat.
//
// Security: the page has no Node access and no network; it can only ask this process for the
// actions in the IPC handlers below. This process reads the plan folder (today.json) and the art
// folder, writes only inbox.jsonl, log.jsonl and persona.json in the plan folder and cut pictures
// in <art folder>/donna-cut, and, for the live chat, runs Claude Code on this computer with a
// read-only tool list. It holds no passwords or tokens.

const { app, BrowserWindow, Notification, dialog, globalShortcut, ipcMain, screen, session } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { cleanFeed, str } = require('./feed');
const Voice = require('./renderer/voice');
const Manifest = require('./renderer/manifest');

const DEFAULTS = {
  feedFolder: '', artFolder: '', sheets: {}, sheet: '', mode: 'card', figure: 'full',
  temperament: 'earned', dials: { ...Voice.DEFAULT_DIALS },
  chat: { mode: 'auto', claudePath: '', repoPath: '', sessionId: '' },
  alwaysOnTop: true, startAtLogin: false, chime: true, warnings: [10, 2], position: null,
};
const FIGURES = new Set(['full', 'scenes', 'bust', 'off']);
const OLD_FIGURES = { auto: 'scenes', close: 'full' }; // earlier versions' choices
const TEMPERS = new Set(['earned', 'angry', 'classic']);
const ACTIONS = new Set(['start', 'done', 'snooze', 'skip', 'undo']);
const IMAGE_EXT = /\.(png|jpe?g|webp)$/i;
const CUT_FILE = /^((?:body|face|scene)\.[a-z]+|bust)__\d+\.(png|jpg)$/;
const MAX_IMAGE_BYTES = 25 * 1024 * 1024;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SAFE_ARG = /^[A-Za-z0-9 ,.:;()'*/_=-]*$/;
// The widget chat can read and plan, never send, post or book: anything else is refused in -p mode.
const CHAT_TOOLS = ['Read', 'Glob', 'Grep', 'WebSearch', 'WebFetch', 'Bash(python3 tools/*)'];
const DEMO = process.argv.includes('--demo'); // sample/today.json, moved to today; nothing is written

let win = null;
let config = { ...DEFAULTS };
let feed = null;
let feedError = '';
let discreet = false;
let timers = [];

const configPath = () => path.join(app.getPath('userData'), 'config.json');

function loadConfig() {
  try {
    const saved = JSON.parse(fs.readFileSync(configPath(), 'utf8'));
    config = { ...DEFAULTS, ...saved, chat: { ...DEFAULTS.chat, ...(saved.chat || {}) } };
    config.dials = Voice.clampDials(config.dials);
    config.figure = OLD_FIGURES[config.figure] || (FIGURES.has(config.figure) ? config.figure : DEFAULTS.figure);
  } catch {
    config = { ...DEFAULTS, chat: { ...DEFAULTS.chat } };
  }
}

function saveConfig() {
  fs.mkdirSync(path.dirname(configPath()), { recursive: true });
  fs.writeFileSync(configPath(), JSON.stringify(config, null, 2), { mode: 0o600 });
}

const isFile = (p) => {
  try {
    return fs.statSync(p).isFile();
  } catch {
    return false;
  }
};

// ---- the plan ------------------------------------------------------------------------------

const feedFolder = () => (DEMO ? path.join(__dirname, 'sample') : config.feedFolder);
const today = () => new Date().toLocaleDateString('en-CA');

function readFeed() {
  feed = null;
  feedError = '';
  if (feedFolder()) {
    try {
      feed = cleanFeed(JSON.parse(fs.readFileSync(path.join(feedFolder(), 'today.json'), 'utf8')));
      if (DEMO) feed.date = today();
    } catch (err) {
      feedError = err.code === 'ENOENT' ? 'No plan yet.' : `Couldn't read today.json: ${err.message}`;
    }
  }
  schedule();
  send('feed', { feed, error: feedError });
}

let watched = '';
function watchFeed() {
  if (watched) fs.unwatchFile(watched);
  watched = feedFolder() ? path.join(feedFolder(), 'today.json') : '';
  // Polling copes with sync clients (Google Drive) that replace the file rather than edit it.
  if (watched) fs.watchFile(watched, { interval: 5000 }, readFeed);
  readFeed();
}

function append(file, record) {
  if (DEMO) return true;
  if (!config.feedFolder) return false;
  fs.appendFileSync(path.join(config.feedFolder, file), JSON.stringify(record) + '\n', { mode: 0o600 });
  return true;
}

// Shrey's tuning, for Donna to read at her next session.
function writePersona() {
  if (DEMO || !config.feedFolder) return;
  const persona = { updated_at: new Date().toISOString(), temperament: config.temperament, dials: config.dials };
  fs.writeFileSync(path.join(config.feedFolder, 'persona.json'), JSON.stringify(persona, null, 2), { mode: 0o600 });
}

// ---- nudges --------------------------------------------------------------------------------

function at(time) {
  const [h, m] = time.split(':').map(Number);
  const d = new Date();
  d.setHours(h, m, 0, 0);
  return d.getTime();
}

function schedule() {
  timers.forEach(clearTimeout);
  timers = [];
  if (!feed || feed.date !== today()) return;
  const now = Date.now();
  const add = (t, nudge) => {
    if (t > now) timers.push(setTimeout(() => fire(nudge), t - now));
  };
  for (const b of feed.blocks) {
    if (b.kind === 'reset') continue;
    add(at(b.start), { id: b.id, kind: b.kind, title: b.title, body: b.first_step || b.title, when: 'now' });
    if (b.kind === 'focus' || b.kind === 'meeting') {
      for (const m of config.warnings) {
        add(at(b.start) - m * 60000, { id: b.id, kind: b.kind, title: `In ${m} min: ${b.title}`, body: b.first_step || '', when: m });
      }
    }
  }
  for (const r of feed.reminders) add(at(r.at), { id: '', kind: 'reminder', title: 'Donna', body: r.text, when: 'now' });
}

function fire(nudge) {
  if (Notification.isSupported()) {
    const n = discreet ? { title: 'Donna', body: 'Something needs you.' } : { title: nudge.title, body: nudge.body || 'Donna' };
    new Notification({ ...n, silent: true }).show(); // the widget plays its own chime
  }
  send('nudge', nudge);
}

// ---- art -----------------------------------------------------------------------------------

function listArt() {
  if (!config.artFolder) return [];
  try {
    return fs.readdirSync(config.artFolder, { withFileTypes: true })
      .filter((e) => e.isFile() && IMAGE_EXT.test(e.name) && !e.name.startsWith('.'))
      .map((e) => ({ name: e.name, size: fs.statSync(path.join(config.artFolder, e.name)).size }))
      .filter((f) => f.size <= MAX_IMAGE_BYTES)
      .slice(0, 100)
      .map((f) => ({ ...f, type: config.sheets[f.name] || '' }));
  } catch {
    return [];
  }
}

function dataUrl(file) {
  const ext = path.extname(file).slice(1).toLowerCase().replace(/^jpg$/, 'jpeg');
  return `data:image/${ext};base64,${fs.readFileSync(file).toString('base64')}`;
}

const cutDir = () => path.join(config.artFolder, 'donna-cut');

function validType(type) {
  if (type === '' || type === 'ignore' || type in Manifest.SHEETS) return true;
  return type.startsWith('slot:') && Manifest.SLOT_RE.test(type.slice(5));
}

function artState() {
  let cuts = 0;
  try {
    cuts = fs.readdirSync(cutDir()).filter((n) => CUT_FILE.test(n)).length;
  } catch {
    cuts = 0;
  }
  return {
    folder: config.artFolder ? path.basename(config.artFolder) : '',
    files: listArt(),
    cuts,
    sheetTypes: Object.fromEntries(Object.entries(Manifest.SHEETS).map(([k, v]) => [k, v.label])),
  };
}

// ---- chat ----------------------------------------------------------------------------------

function findClaude() {
  if (config.chat.claudePath && isFile(config.chat.claudePath)) return config.chat.claudePath;
  const names = process.platform === 'win32' ? ['claude.exe', 'claude.cmd'] : ['claude'];
  const home = os.homedir();
  const dirs = [
    ...(process.env.PATH || '').split(path.delimiter),
    path.join(home, '.local', 'bin'), path.join(home, '.claude', 'local'),
    process.env.APPDATA ? path.join(process.env.APPDATA, 'npm') : '', '/opt/homebrew/bin', '/usr/local/bin',
  ].filter(Boolean);
  for (const d of dirs) for (const n of names) if (isFile(path.join(d, n))) return path.join(d, n);
  return '';
}

const hasDonna = (dir) => Boolean(dir) && isFile(path.join(dir, '.claude', 'agents', 'donna.md'));

function repoPath() {
  if (hasDonna(config.chat.repoPath)) return config.chat.repoPath;
  const parent = path.resolve(__dirname, '..');
  return hasDonna(parent) ? parent : '';
}

function chatStatus() {
  const claude = findClaude();
  const repo = repoPath();
  const live = config.chat.mode !== 'inbox' && Boolean(claude && repo) && !DEMO;
  let note = 'Messages go to Donna at her next check-in.';
  if (live) note = 'Live: Donna answers through Claude Code on this computer.';
  else if (config.chat.mode === 'inbox') note = 'Messages only: Donna answers at her next check-in.';
  else if (!claude) note = 'Claude Code not found, so messages wait for her next check-in.';
  else if (!repo) note = "Choose the folder with Donna's files to chat live.";
  return { live, note, claude: claude ? path.basename(claude) : '', repo: repo ? path.basename(repo) : '', mode: config.chat.mode };
}

function runClaude(text) {
  return new Promise((resolve) => {
    const exe = findClaude();
    const cwd = repoPath();
    if (!exe || !cwd) {
      resolve({ error: 'Claude Code is not set up for the chat.' });
      return;
    }
    const args = ['-p', '--output-format', 'json', '--agent', 'donna', '--permission-mode', 'default',
      '--append-system-prompt', Voice.chatBrief(config.dials, config.temperament)];
    if (UUID.test(config.chat.sessionId)) args.push('--resume', config.chat.sessionId);
    args.push('--allowedTools', ...CHAT_TOOLS);
    // .cmd launchers on Windows need a shell; only fixed, checked arguments go on that command line.
    // The message itself always goes through stdin, never the command line.
    const viaShell = process.platform === 'win32' && /\.(cmd|bat)$/i.test(exe);
    if (viaShell && !args.every((a) => SAFE_ARG.test(a))) {
      resolve({ error: 'Refused to start Claude Code with an unexpected argument.' });
      return;
    }
    const quoted = viaShell ? args.map((a) => (/[\s()*]/.test(a) ? `"${a}"` : a)) : args;
    let child;
    try {
      child = spawn(viaShell ? `"${exe}"` : exe, quoted, { cwd, shell: viaShell, windowsHide: true, env: process.env });
    } catch (err) {
      resolve({ error: `Couldn't start Claude Code: ${err.message}` });
      return;
    }
    let out = '';
    let errText = '';
    const timer = setTimeout(() => child.kill(), 180 * 1000);
    child.stdout.on('data', (d) => {
      if (out.length < 2e6) out += d;
    });
    child.stderr.on('data', (d) => {
      if (errText.length < 65536) errText += d;
    });
    child.on('error', (err) => {
      clearTimeout(timer);
      resolve({ error: `Couldn't start Claude Code: ${err.message}` });
    });
    child.on('close', (code) => {
      clearTimeout(timer);
      try {
        const r = JSON.parse(out.trim().split('\n').pop());
        if (UUID.test(r.session_id || '')) {
          config.chat.sessionId = r.session_id;
          saveConfig();
        }
        if (r.is_error) resolve({ error: str(String(r.result || 'Claude Code reported an error.'), 600) });
        else resolve({ reply: str(String(r.result || ''), 4000), via: 'claude' });
      } catch {
        resolve({ error: code === null ? 'Donna took too long and was stopped.' : `Claude Code stopped (${code}). ${str(errText, 300)}` });
      }
    });
    child.stdin.on('error', () => {});
    child.stdin.end(text);
  });
}

// ---- window --------------------------------------------------------------------------------

function send(channel, data) {
  if (win && !win.isDestroyed()) win.webContents.send(channel, data);
}

function size() {
  const area = screen.getPrimaryDisplay().workArea;
  const height = Math.min(740, area.height - 40);
  if (config.mode === 'mini') return { width: 400, height: 116 };
  return { width: config.figure === 'off' ? 440 : 720, height };
}

function place() {
  const s = size();
  const area = screen.getPrimaryDisplay().workArea;
  const p = config.position;
  const onScreen = p && screen.getAllDisplays().some((d) => {
    const a = d.workArea;
    return p.x >= a.x && p.y >= a.y && p.x + 40 <= a.x + a.width && p.y + 40 <= a.y + a.height;
  });
  return onScreen ? { ...s, x: p.x, y: p.y } : { ...s, x: area.x + area.width - s.width - 24, y: area.y + area.height - s.height - 24 };
}

function resize() {
  const s = size();
  const [x, y] = win.getPosition();
  const [, h] = win.getSize();
  const area = screen.getPrimaryDisplay().workArea;
  const nx = Math.min(x, area.x + area.width - s.width);
  win.setBounds({ x: Math.max(area.x, nx), y: Math.max(area.y, y + h - s.height), width: s.width, height: s.height });
}

function createWindow() {
  win = new BrowserWindow({
    ...place(),
    frame: false,
    transparent: true,
    resizable: false,
    maximizable: false,
    fullscreenable: false,
    hasShadow: false,
    show: false,
    title: 'Donna',
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
      autoplayPolicy: 'no-user-gesture-required', // the chime on a nudge
      devTools: !app.isPackaged,
    },
  });
  win.setAlwaysOnTop(config.alwaysOnTop, 'floating');
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  win.once('ready-to-show', () => win.show());
  win.on('moved', () => {
    const [x, y] = win.getPosition();
    config.position = { x, y };
    saveConfig();
  });
}

// ---- IPC: the only things the page can ask for ------------------------------------------

function fromOurPage(event) {
  return win && event.sender === win.webContents && event.senderFrame === win.webContents.mainFrame;
}

function handle(channel, fn) {
  ipcMain.handle(channel, (event, ...args) => {
    if (!fromOurPage(event)) throw new Error('refused');
    return fn(...args);
  });
}

function publicConfig() {
  const { mode, figure, temperament, dials, alwaysOnTop, startAtLogin, chime } = config;
  return {
    mode, figure, temperament, dials, alwaysOnTop, startAtLogin, chime, demo: DEMO,
    hasFolder: Boolean(feedFolder()), artFolder: config.artFolder ? path.basename(config.artFolder) : '', chat: chatStatus(),
  };
}

function legacySheet() {
  // Before the art folder, the widget took a single character sheet.
  if (config.artFolder || !config.sheet || !isFile(config.sheet) || !IMAGE_EXT.test(config.sheet)) return null;
  return fs.statSync(config.sheet).size <= MAX_IMAGE_BYTES ? dataUrl(config.sheet) : null;
}

function registerIpc() {
  handle('get-state', () => ({ config: publicConfig(), feed, error: feedError, discreet, legacySheet: legacySheet() }));

  handle('pick-folder', async () => {
    const r = await dialog.showOpenDialog(win, { title: "Choose Donna's plan folder (Donna/widget in Google Drive)", properties: ['openDirectory'] });
    if (!r.canceled && r.filePaths[0]) {
      config.feedFolder = r.filePaths[0];
      saveConfig();
      watchFeed();
      writePersona();
    }
    return publicConfig();
  });

  handle('pick-art', async () => {
    const r = await dialog.showOpenDialog(win, { title: "Choose the folder with Donna's pictures", properties: ['openDirectory'] });
    if (!r.canceled && r.filePaths[0]) {
      config.artFolder = r.filePaths[0];
      for (const f of listArt()) if (!config.sheets[f.name]) config.sheets[f.name] = Manifest.guess(f.name) || '';
      saveConfig();
    }
    return artState();
  });

  handle('art-state', () => artState());

  handle('art-image', (name) => {
    const file = listArt().find((f) => f.name === name);
    if (!file || path.basename(String(name)) !== name) throw new Error('not in the art folder');
    return dataUrl(path.join(config.artFolder, file.name));
  });

  handle('art-cuts', () => {
    if (!config.artFolder) return [];
    try {
      return fs.readdirSync(cutDir())
        .filter((n) => CUT_FILE.test(n))
        .slice(0, 400)
        .filter((n) => fs.statSync(path.join(cutDir(), n)).size <= MAX_IMAGE_BYTES)
        .map((n) => ({ slot: n.split('__')[0], url: dataUrl(path.join(cutDir(), n)), cutout: n.endsWith('.png') }));
    } catch {
      return [];
    }
  });

  handle('art-save', (pieces) => {
    if (!config.artFolder || !Array.isArray(pieces) || pieces.length > 400) throw new Error('nothing to save');
    fs.mkdirSync(cutDir(), { recursive: true });
    for (const n of fs.readdirSync(cutDir())) if (CUT_FILE.test(n)) fs.unlinkSync(path.join(cutDir(), n));
    const counts = {};
    let saved = 0;
    for (const p of pieces) {
      const m = /^data:image\/(png|jpeg);base64,([A-Za-z0-9+/=]+)$/.exec(String(p && p.url));
      if (!m || !Manifest.SLOT_RE.test(String(p.slot))) continue;
      const bytes = Buffer.from(m[2], 'base64');
      if (bytes.length > MAX_IMAGE_BYTES) continue;
      counts[p.slot] = (counts[p.slot] || 0) + 1;
      fs.writeFileSync(path.join(cutDir(), `${p.slot}__${counts[p.slot]}.${m[1] === 'png' ? 'png' : 'jpg'}`), bytes);
      saved += 1;
    }
    return saved;
  });

  handle('pick-repo', async () => {
    const r = await dialog.showOpenDialog(win, { title: "Choose the folder with Donna's files (the repository)", properties: ['openDirectory'] });
    if (!r.canceled && r.filePaths[0]) {
      if (!hasDonna(r.filePaths[0])) throw new Error("That folder doesn't have .claude/agents/donna.md.");
      config.chat.repoPath = r.filePaths[0];
      saveConfig();
    }
    return publicConfig();
  });

  handle('pick-claude', async () => {
    const r = await dialog.showOpenDialog(win, { title: 'Find Claude Code (claude, claude.exe or claude.cmd)', properties: ['openFile'] });
    if (!r.canceled && r.filePaths[0]) {
      if (!/^claude(\.exe|\.cmd)?$/i.test(path.basename(r.filePaths[0]))) throw new Error("That isn't Claude Code.");
      config.chat.claudePath = r.filePaths[0];
      saveConfig();
    }
    return publicConfig();
  });

  handle('chat-send', async (text) => {
    const clean = str(text, 4000).trim();
    if (!clean) return { error: 'Nothing to send.' };
    if (chatStatus().live) return runClaude(clean);
    const ok = append('inbox.jsonl', { at: new Date().toISOString(), text: clean, via: 'chat' });
    return ok ? { via: 'inbox' } : { error: 'Choose the plan folder in Settings first.' };
  });

  handle('chat-reset', () => {
    config.chat.sessionId = '';
    saveConfig();
    return true;
  });

  handle('set', (key, value) => {
    if (key === 'mode' && ['card', 'mini'].includes(value)) {
      config.mode = value;
      resize();
    } else if (key === 'figure' && FIGURES.has(value)) {
      config.figure = value;
      resize();
    } else if (key === 'temperament' && TEMPERS.has(value)) {
      config.temperament = value;
      writePersona();
    } else if (key === 'dials' && value && typeof value === 'object') {
      config.dials = Voice.clampDials(value);
      writePersona();
    } else if (key === 'sheetType' && value && typeof value === 'object') {
      if (!listArt().some((f) => f.name === value.name) || !validType(String(value.type))) throw new Error('bad picture type');
      config.sheets[value.name] = String(value.type);
    } else if (key === 'chatMode' && ['auto', 'inbox'].includes(value)) {
      config.chat.mode = value;
    } else if (key === 'alwaysOnTop' && typeof value === 'boolean') {
      config.alwaysOnTop = value;
      win.setAlwaysOnTop(value, 'floating');
    } else if (key === 'startAtLogin' && typeof value === 'boolean') {
      config.startAtLogin = value;
      if (process.platform !== 'linux') app.setLoginItemSettings({ openAtLogin: value });
    } else if (key === 'chime' && typeof value === 'boolean') {
      config.chime = value;
    } else if (key === 'discreet' && typeof value === 'boolean') {
      discreet = value; // not saved: every start is in normal mode
      return publicConfig();
    } else {
      throw new Error('unknown setting');
    }
    saveConfig();
    return publicConfig();
  });

  handle('log', (blockId, action) => {
    if (!ACTIONS.has(action)) throw new Error('unknown action');
    return append('log.jsonl', { at: new Date().toISOString(), date: today(), block: str(blockId, 24), action });
  });

  handle('notify', (title, body) => {
    fire({ id: '', kind: 'reminder', title: str(title, 80) || 'Donna', body: str(body, 140), when: 'now' });
    return true;
  });

  handle('quit', () => app.quit());
}

// ---- lockdown and start-up -----------------------------------------------------------------

app.enableSandbox();
if (!app.requestSingleInstanceLock()) app.quit();

app.on('web-contents-created', (_e, contents) => {
  contents.setWindowOpenHandler(() => ({ action: 'deny' }));
  contents.on('will-navigate', (e) => e.preventDefault());
  contents.on('will-redirect', (e) => e.preventDefault());
  contents.on('will-attach-webview', (e) => e.preventDefault());
});

app.whenReady().then(() => {
  // No permissions (camera, microphone, location...) and no network for the page: local files only.
  session.defaultSession.setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
  session.defaultSession.setPermissionCheckHandler(() => false);
  session.defaultSession.webRequest.onBeforeRequest((details, callback) => {
    callback({ cancel: !/^(file|devtools|data):/i.test(details.url) });
  });

  loadConfig();
  registerIpc();
  createWindow();
  watchFeed();

  globalShortcut.register('CommandOrControl+Shift+D', () => {
    discreet = !discreet;
    send('discreet', discreet);
  });

  // Re-arm the day's nudges just after midnight, and after the machine wakes from sleep.
  setInterval(() => {
    if (feed && feed.date !== today()) schedule();
  }, 60 * 1000);
  require('electron').powerMonitor.on('resume', readFeed);
});

app.on('second-instance', () => win && win.show());
app.on('will-quit', () => globalShortcut.unregisterAll());
app.on('window-all-closed', () => app.quit());

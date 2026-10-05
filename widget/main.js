'use strict';
// Donna's desktop widget: shows today's plan from a synced folder and nudges on time.
//
// Security: the page has no Node access and no network; it can only ask this process for the
// actions in the IPC handlers below. This process reads one folder (today.json) and one image
// (the character sheet), and appends to two files there (inbox.jsonl, log.jsonl). Nothing else.

const { app, BrowserWindow, Notification, dialog, globalShortcut, ipcMain, screen, session } = require('electron');
const fs = require('fs');
const path = require('path');
const { cleanFeed, str } = require('./feed');

const SIZES = { card: { width: 380, height: 660 }, mini: { width: 380, height: 116 } };
const DEFAULTS = {
  feedFolder: '', sheet: '', layout: 'angry', mode: 'card', alwaysOnTop: true, startAtLogin: false,
  chime: true, warnings: [10, 2], position: null,
};
const ACTIONS = new Set(['start', 'done', 'snooze', 'skip', 'undo']);
const MAX_SHEET_BYTES = 15 * 1024 * 1024;
const DEMO = process.argv.includes('--demo'); // sample/today.json, moved to today; nothing is written

let win = null;
let config = { ...DEFAULTS };
let feed = null;
let feedError = '';
let sheet = null; // data URL
let discreet = false;
let timers = [];

const configPath = () => path.join(app.getPath('userData'), 'config.json');

function loadConfig() {
  try {
    const saved = JSON.parse(fs.readFileSync(configPath(), 'utf8'));
    config = { ...DEFAULTS, ...saved };
  } catch {
    config = { ...DEFAULTS };
  }
}

function saveConfig() {
  fs.mkdirSync(path.dirname(configPath()), { recursive: true });
  fs.writeFileSync(configPath(), JSON.stringify(config, null, 2), { mode: 0o600 });
}

// ---- the feed -----------------------------------------------------------------------------

const feedFolder = () => (DEMO ? path.join(__dirname, 'sample') : config.feedFolder);

function readFeed() {
  feed = null;
  feedError = '';
  if (!feedFolder()) return;
  try {
    const text = fs.readFileSync(path.join(feedFolder(), 'today.json'), 'utf8');
    feed = cleanFeed(JSON.parse(text));
    if (DEMO) feed.date = today();
  } catch (err) {
    feedError = err.code === 'ENOENT' ? 'No plan yet.' : `Couldn't read today.json: ${err.message}`;
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

function readSheet() {
  sheet = null;
  if (!config.sheet) return;
  try {
    const stat = fs.statSync(config.sheet);
    if (stat.size > MAX_SHEET_BYTES) throw new Error('too large');
    const ext = path.extname(config.sheet).slice(1).toLowerCase().replace('jpg', 'jpeg');
    if (!['png', 'jpeg', 'webp'].includes(ext)) throw new Error('not a PNG, JPEG or WebP');
    sheet = `data:image/${ext};base64,${fs.readFileSync(config.sheet).toString('base64')}`;
  } catch {
    sheet = null;
  }
}

// ---- nudges -------------------------------------------------------------------------------

const today = () => new Date().toLocaleDateString('en-CA');
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
    const n = discreet
      ? { title: 'Donna', body: 'Something needs you.' }
      : { title: nudge.title, body: nudge.body || 'Donna' };
    new Notification({ ...n, silent: true }).show(); // the widget plays its own chime
  }
  send('nudge', nudge);
}

// ---- window -------------------------------------------------------------------------------

function send(channel, data) {
  if (win && !win.isDestroyed()) win.webContents.send(channel, data);
}

function place(mode) {
  const size = SIZES[mode];
  const area = screen.getPrimaryDisplay().workArea;
  const p = config.position;
  const onScreen = p && screen.getAllDisplays().some((d) => {
    const a = d.workArea;
    return p.x >= a.x && p.y >= a.y && p.x + 40 <= a.x + a.width && p.y + 40 <= a.y + a.height;
  });
  return onScreen ? { ...size, x: p.x, y: p.y } : { ...size, x: area.x + area.width - size.width - 24, y: area.y + area.height - size.height - 24 };
}

function createWindow() {
  win = new BrowserWindow({
    ...place(config.mode),
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

// ---- IPC: the only things the page can ask for ------------------------------------------------

function fromOurPage(event) {
  return win && event.sender === win.webContents && event.senderFrame === win.webContents.mainFrame;
}

function handle(channel, fn) {
  ipcMain.handle(channel, (event, ...args) => {
    if (!fromOurPage(event)) throw new Error('refused');
    return fn(...args);
  });
}

function append(file, record) {
  if (DEMO) return true;
  if (!config.feedFolder) return false;
  fs.appendFileSync(path.join(config.feedFolder, file), JSON.stringify(record) + '\n', { mode: 0o600 });
  return true;
}

function publicConfig() {
  const { layout, mode, alwaysOnTop, startAtLogin, chime } = config;
  return { layout, mode, alwaysOnTop, startAtLogin, chime, demo: DEMO, hasFolder: Boolean(feedFolder()), hasSheet: Boolean(sheet) };
}

function registerIpc() {
  handle('get-state', () => ({ config: publicConfig(), feed, error: feedError, sheet, discreet }));

  handle('pick-folder', async () => {
    const r = await dialog.showOpenDialog(win, { title: "Choose Donna's widget folder (Donna/widget in Google Drive)", properties: ['openDirectory'] });
    if (r.canceled || !r.filePaths[0]) return publicConfig();
    config.feedFolder = r.filePaths[0];
    saveConfig();
    watchFeed();
    return publicConfig();
  });

  handle('pick-sheet', async () => {
    const r = await dialog.showOpenDialog(win, {
      title: "Choose Donna's character sheet", properties: ['openFile'],
      filters: [{ name: 'Images', extensions: ['png', 'jpg', 'jpeg', 'webp'] }],
    });
    if (r.canceled || !r.filePaths[0]) return { config: publicConfig(), sheet };
    config.sheet = r.filePaths[0];
    saveConfig();
    readSheet();
    return { config: publicConfig(), sheet };
  });

  handle('set', (key, value) => {
    if (key === 'layout' && ['angry', 'classic'].includes(value)) config.layout = value;
    else if (key === 'mode' && value in SIZES) {
      config.mode = value;
      const b = place(value);
      win.setBounds({ x: win.getPosition()[0], y: win.getPosition()[1] + (win.getSize()[1] - b.height), width: b.width, height: b.height });
    } else if (key === 'alwaysOnTop' && typeof value === 'boolean') {
      config.alwaysOnTop = value;
      win.setAlwaysOnTop(value, 'floating');
    } else if (key === 'startAtLogin' && typeof value === 'boolean') {
      config.startAtLogin = value;
      if (process.platform !== 'linux') app.setLoginItemSettings({ openAtLogin: value });
    } else if (key === 'chime' && typeof value === 'boolean') config.chime = value;
    else if (key === 'discreet' && typeof value === 'boolean') {
      discreet = value; // not saved: every start is in normal mode
      return publicConfig();
    } else throw new Error('unknown setting');
    saveConfig();
    return publicConfig();
  });

  handle('capture', (text) => {
    const clean = str(text, 500).trim();
    if (!clean) return false;
    return append('inbox.jsonl', { at: new Date().toISOString(), text: clean });
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

// ---- lockdown and start-up ----------------------------------------------------------------

app.enableSandbox();
if (!app.requestSingleInstanceLock()) app.quit();

app.on('web-contents-created', (_e, contents) => {
  contents.setWindowOpenHandler(() => ({ action: 'deny' }));
  contents.on('will-navigate', (e) => e.preventDefault());
  contents.on('will-redirect', (e) => e.preventDefault());
  contents.on('will-attach-webview', (e) => e.preventDefault());
});

app.whenReady().then(() => {
  // No permissions (camera, microphone, location...) and no network: only local files load.
  session.defaultSession.setPermissionRequestHandler((_wc, _permission, callback) => callback(false));
  session.defaultSession.setPermissionCheckHandler(() => false);
  session.defaultSession.webRequest.onBeforeRequest((details, callback) => {
    callback({ cancel: !/^(file|devtools|data):/i.test(details.url) });
  });

  loadConfig();
  readSheet();
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

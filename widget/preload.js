'use strict';
// The page's only window to the outside: a short list of named actions, nothing else.
const { contextBridge, ipcRenderer } = require('electron');

const CHANNELS = new Set(['feed', 'nudge', 'discreet']);

contextBridge.exposeInMainWorld('donna', {
  state: () => ipcRenderer.invoke('get-state'),
  pickFolder: () => ipcRenderer.invoke('pick-folder'),
  pickSheet: () => ipcRenderer.invoke('pick-sheet'),
  set: (key, value) => ipcRenderer.invoke('set', String(key), value),
  capture: (text) => ipcRenderer.invoke('capture', String(text)),
  log: (blockId, action) => ipcRenderer.invoke('log', String(blockId), String(action)),
  notify: (title, body) => ipcRenderer.invoke('notify', String(title), String(body)),
  quit: () => ipcRenderer.invoke('quit'),
  on: (channel, fn) => {
    if (CHANNELS.has(channel)) ipcRenderer.on(channel, (_event, data) => fn(data));
  },
});

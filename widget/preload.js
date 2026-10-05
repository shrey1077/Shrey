'use strict';
// The page's only window to the outside: a short list of named actions, nothing else.
const { contextBridge, ipcRenderer } = require('electron');

const CHANNELS = new Set(['feed', 'nudge', 'discreet']);

contextBridge.exposeInMainWorld('donna', {
  state: () => ipcRenderer.invoke('get-state'),
  pickFolder: () => ipcRenderer.invoke('pick-folder'),
  pickArt: () => ipcRenderer.invoke('pick-art'),
  artState: () => ipcRenderer.invoke('art-state'),
  artImage: (name) => ipcRenderer.invoke('art-image', String(name)),
  artCuts: () => ipcRenderer.invoke('art-cuts'),
  artSave: (pieces) => ipcRenderer.invoke('art-save', pieces),
  pickRepo: () => ipcRenderer.invoke('pick-repo'),
  pickClaude: () => ipcRenderer.invoke('pick-claude'),
  chatSend: (text) => ipcRenderer.invoke('chat-send', String(text)),
  chatReset: () => ipcRenderer.invoke('chat-reset'),
  set: (key, value) => ipcRenderer.invoke('set', String(key), value),
  log: (blockId, action) => ipcRenderer.invoke('log', String(blockId), String(action)),
  notify: (title, body) => ipcRenderer.invoke('notify', String(title), String(body)),
  quit: () => ipcRenderer.invoke('quit'),
  on: (channel, fn) => {
    if (CHANNELS.has(channel)) ipcRenderer.on(channel, (_event, data) => fn(data));
  },
});

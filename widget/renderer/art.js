'use strict';
// Cuts Donna's art sheets into emotions and scenes (see manifest.js) and serves the right picture
// for the moment. Runs in the page: images come in as data URLs from the app, and the cut pieces go
// back to the app, which saves them in <art folder>/donna-cut so they load instantly next time.

const Art = (() => {
  const BASE_W = 1536;
  const BASE_H = 1024;
  const MAX_H = 760; // cut pieces are scaled down to this height
  const EXPRESSION_ORDER = ['normal', 'amused', 'serious', 'thoughtful', 'suspicious', 'surprised', 'happy', 'angry'];
  let slots = {}; // slot -> [{ url, cutout }]

  const hash = (s) => [...String(s)].reduce((a, c) => (Math.imul(a, 31) + c.charCodeAt(0)) >>> 0, 2166136261);
  const light = (d, i) => d[i] > 225 && d[i + 1] > 218 && d[i + 2] > 205;
  const paper = (d, i) => d[i] > 220 && d[i + 1] > 210 && d[i + 2] > 195 && Math.abs(d[i] - d[i + 2]) < 40;

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error('could not read the image'));
      img.src = url;
    });
  }

  function pixels(img) {
    const c = document.createElement('canvas');
    c.width = img.naturalWidth;
    c.height = img.naturalHeight;
    const ctx = c.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0);
    return { canvas: c, data: ctx.getImageData(0, 0, c.width, c.height).data, W: c.width, H: c.height };
  }

  // Move each edge of a rough rectangle onto the light gutter between panels, if one is near.
  function snap(px, rect) {
    const { data, W, H } = px;
    let [x0, y0, w, h] = rect;
    let x1 = x0 + w;
    let y1 = y0 + h;
    const R = Math.round(18 * (W / BASE_W));
    const col = (x, a, b) => {
      let n = 0;
      let t = 0;
      for (let y = Math.max(0, a); y < Math.min(H, b); y += 3) {
        t += 1;
        if (light(data, (y * W + x) * 4)) n += 1;
      }
      return t ? n / t : 0;
    };
    const row = (y, a, b) => {
      let n = 0;
      let t = 0;
      for (let x = Math.max(0, a); x < Math.min(W, b); x += 3) {
        t += 1;
        if (light(data, (y * W + x) * 4)) n += 1;
      }
      return t ? n / t : 0;
    };
    const near = (from, to, test) => {
      const step = from < to ? 1 : -1;
      for (let v = from; v !== to; v += step) if (test(v)) return v;
      return null;
    };
    const clampX = (v) => Math.max(0, Math.min(W - 1, v));
    const clampY = (v) => Math.max(0, Math.min(H - 1, v));
    let g = near(clampX(x0 + R), clampX(x0 - R), (x) => col(x, y0, y1) > 0.9);
    if (g !== null) x0 = g + 1;
    g = near(clampX(x1 - R), clampX(x1 + R), (x) => col(x, y0, y1) > 0.9);
    if (g !== null) x1 = g;
    g = near(clampY(y0 + R), clampY(y0 - R), (y) => row(y, x0, x1) > 0.9);
    if (g !== null) y0 = g + 1;
    g = near(clampY(y1 - R), clampY(y1 + R), (y) => row(y, x0, x1) > 0.9);
    if (g !== null) y1 = g;
    const inset = 2;
    return [x0 + inset, y0 + inset, Math.max(8, x1 - x0 - 2 * inset), Math.max(8, y1 - y0 - 2 * inset)];
  }

  // The character sheet's EXPRESSIONS row, found from the picture itself.
  function findExpressions(px) {
    const { data, W, H } = px;
    const x0 = Math.round(W * 0.3);
    const covered = (y) => {
      let pic = 0;
      let n = 0;
      for (let x = x0; x < W; x += 3) {
        n += 1;
        if (!paper(data, (y * W + x) * 4)) pic += 1;
      }
      return pic / n;
    };
    let best = [0, 0];
    let start = -1;
    for (let y = Math.round(H * 0.45); y <= Math.round(H * 0.8); y += 1) {
      if (covered(y) > 0.85 && y < Math.round(H * 0.8)) {
        if (start < 0) start = y;
      } else if (start >= 0) {
        if (y - start > best[1] - best[0]) best = [start, y];
        start = -1;
      }
    }
    const [top, bottom] = best;
    if (bottom - top < H * 0.08) return null;
    const mid = Math.round((top + bottom) / 2);
    const runs = [];
    let run = -1;
    for (let x = x0; x <= W; x += 1) {
      const pic = x < W && !paper(data, (mid * W + x) * 4);
      if (pic && run < 0) run = x;
      if (!pic && run >= 0) {
        if (x - run > W * 0.04) runs.push([run, x]);
        run = -1;
      }
    }
    if (runs.length !== EXPRESSION_ORDER.length) return null;
    return runs.map(([a, b]) => [a + 2, top + 2, b - a - 4, bottom - top - 4]);
  }

  // Make the paper around a figure transparent, starting from the edges so a white blouse stays.
  function keyPaper(ctx, w, h) {
    const img = ctx.getImageData(0, 0, w, h);
    const d = img.data;
    const seen = new Uint8Array(w * h);
    const stack = [];
    for (let x = 0; x < w; x += 1) stack.push(x, (h - 1) * w + x);
    for (let y = 0; y < h; y += 1) stack.push(y * w, y * w + w - 1);
    while (stack.length) {
      const p = stack.pop();
      if (seen[p]) continue;
      seen[p] = 1;
      if (!paper(d, p * 4)) continue;
      d[p * 4 + 3] = 0;
      const x = p % w;
      if (x > 0) stack.push(p - 1);
      if (x < w - 1) stack.push(p + 1);
      if (p >= w) stack.push(p - w);
      if (p < w * (h - 1)) stack.push(p + w);
    }
    // Soften the rim: light pixels touching the removed paper fade out instead of leaving a halo.
    for (let pass = 0; pass < 2; pass += 1) {
      const clear = new Uint8Array(w * h);
      for (let p = 0; p < w * h; p += 1) clear[p] = d[p * 4 + 3] === 0 ? 1 : 0;
      for (let p = 0; p < w * h; p += 1) {
        if (clear[p]) continue;
        const x = p % w;
        const edge = (x > 0 && clear[p - 1]) || (x < w - 1 && clear[p + 1]) || (p >= w && clear[p - w]) || (p < w * (h - 1) && clear[p + w]);
        if (!edge) continue;
        const lum = (d[p * 4] + d[p * 4 + 1] + d[p * 4 + 2]) / 3;
        if (lum > 200) d[p * 4 + 3] = 0;
        else if (lum > 160) d[p * 4 + 3] = Math.min(d[p * 4 + 3], 120);
      }
    }
    ctx.putImageData(img, 0, 0);
  }

  function crop(px, [x, y, w, h], opts = {}) {
    const scale = Math.min(1, MAX_H / h);
    const c = document.createElement('canvas');
    c.width = Math.max(1, Math.round(w * scale));
    c.height = Math.max(1, Math.round(h * scale));
    const ctx = c.getContext('2d', { willReadFrequently: Boolean(opts.key) });
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(px.canvas, x, y, w, h, 0, 0, c.width, c.height);
    if (opts.key === 'paper') keyPaper(ctx, c.width, c.height);
    return { url: opts.key ? c.toDataURL('image/png') : c.toDataURL('image/jpeg', 0.9), cutout: Boolean(opts.key) };
  }

  // Cut one sheet. `type` is a key of Manifest.SHEETS. Returns [{ slot, url, cutout }].
  async function cutSheet(url, type) {
    const sheet = Manifest.SHEETS[type];
    if (!sheet) return [];
    const px = pixels(await loadImage(url));
    const sx = px.W / BASE_W;
    const sy = px.H / BASE_H;
    const found = type === 'character' ? findExpressions(px) : null;
    let face = 0;
    const out = [];
    for (const [slot, rect, opts = {}] of sheet.cuts) {
      let r = [rect[0] * sx, rect[1] * sy, rect[2] * sx, rect[3] * sy].map(Math.round);
      if (found && slot.startsWith('face.')) {
        r = found[face];
        face += 1;
      } else if (!opts.key) {
        r = snap(px, r);
      }
      out.push({ slot, ...crop(px, r, opts) });
    }
    return out;
  }

  // A single picture used whole for one slot, scaled down; keeps transparency if it has any.
  async function single(url, slot) {
    const img = await loadImage(url);
    const scale = Math.min(1, MAX_H / img.naturalHeight);
    const c = document.createElement('canvas');
    c.width = Math.max(1, Math.round(img.naturalWidth * scale));
    c.height = Math.max(1, Math.round(img.naturalHeight * scale));
    const ctx = c.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, c.width, c.height);
    const cutout = ctx.getImageData(0, 0, 1, 1).data[3] < 250;
    return { slot, url: cutout ? c.toDataURL('image/png') : c.toDataURL('image/jpeg', 0.9), cutout };
  }

  function reset() {
    slots = {};
  }

  function add(slot, item) {
    if (!Manifest.SLOT_RE.test(slot) || !item || !item.url) return;
    (slots[slot] = slots[slot] || []).push({ url: item.url, cutout: Boolean(item.cutout) });
  }

  const has = (slot) => Boolean(slots[slot] && slots[slot].length);
  const count = () => Object.values(slots).reduce((n, list) => n + list.length, 0);
  const list = () => Object.keys(slots).sort();

  function pick(slot, seed = '') {
    const items = slots[slot];
    return items && items.length ? items[hash(`${seed}|${slot}`) % items.length] : null;
  }

  // The best picture of a kind ('body' or 'face') for an emotion, walking the fallbacks.
  function find(kind, emotion, seed = '') {
    for (const e of Manifest.chain(emotion)) {
      const item = pick(`${kind}.${e}`, seed);
      if (item) return { ...item, slot: `${kind}.${e}` };
    }
    return null;
  }

  function paintFace(el, emotion, seed = '') {
    const item = find('face', emotion, seed) || pick('bust', seed) || find('body', emotion, seed);
    const url = item ? item.url : '';
    if (el.dataset.url !== url) {
      el.style.backgroundImage = url ? `url("${url}")` : '';
      el.dataset.url = url;
    }
    el.dataset.face = item ? emotion : 'none';
  }

  return { cutSheet, single, reset, add, has, count, list, pick, find, paintFace };
})();

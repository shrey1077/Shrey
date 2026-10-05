'use strict';
// Finds the eight expression panels on Donna's character sheet and paints them as avatars.
//
// Both sheets put EXPRESSIONS in one row, in the same order. The panels are found by scanning for
// the band of picture between the cream paper; if that fails (an unusual image), measured
// positions for a 1536x1024 sheet are scaled to the image instead.

const Faces = (() => {
  const NAMES = ['neutral', 'amused', 'serious', 'thoughtful', 'suspicious', 'surprised', 'happy', 'intimidating'];
  const LABELS = {
    angry: ['Neutral / angry', 'Amused / angry', 'Serious / angry', 'Thoughtful / angry', 'Suspicious / angry',
      'Surprised / angry', 'Happy / angry', 'Intimidating'],
    classic: ['Confident', 'Amused', 'Serious', 'Thoughtful', 'Suspicious', 'Surprised', 'Warm smile', 'Intimidating'],
  };
  // [x, y, width, height] on a 1536x1024 sheet.
  const FALLBACK = {
    classic: [[478, 548, 120, 146], [606, 548, 117, 146], [730, 548, 120, 146], [858, 548, 120, 146],
      [985, 548, 124, 146], [1116, 548, 120, 146], [1243, 548, 123, 146], [1374, 548, 147, 146]],
    angry: [[476, 544, 118, 145], [602, 544, 118, 145], [729, 544, 118, 145], [855, 544, 122, 145],
      [987, 544, 121, 145], [1119, 544, 127, 145], [1255, 544, 129, 145], [1393, 544, 132, 145]],
  };

  let sheet = null; // { url, width, height, rects: { name: [x, y, w, h] } }

  const isPaper = (d, i) => d[i] > 220 && d[i + 1] > 210 && d[i + 2] > 195 && Math.abs(d[i] - d[i + 2]) < 40;

  function detect(img) {
    const W = img.naturalWidth;
    const H = img.naturalHeight;
    const canvas = document.createElement('canvas');
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0);
    let data;
    try {
      data = ctx.getImageData(0, 0, W, H).data;
    } catch {
      return null; // a tainted canvas (file:// in a plain browser): use the fallback
    }
    const x0 = Math.round(W * 0.3);
    const covered = (y) => {
      let pic = 0;
      let n = 0;
      for (let x = x0; x < W; x += 3) {
        n += 1;
        if (!isPaper(data, (y * W + x) * 4)) pic += 1;
      }
      return pic / n;
    };
    // The expressions row: the tallest run of rows in the lower half that is nearly all picture.
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
      const pic = x < W && !isPaper(data, (mid * W + x) * 4);
      if (pic && run < 0) run = x;
      if (!pic && run >= 0) {
        if (x - run > W * 0.04) runs.push([run, x]);
        run = -1;
      }
    }
    if (runs.length !== NAMES.length) return null;
    const inset = 2;
    return runs.map(([a, b]) => [a + inset, top + inset, b - a - 2 * inset, bottom - top - 2 * inset]);
  }

  function load(url, layout) {
    return new Promise((resolve) => {
      if (!url) {
        sheet = null;
        resolve(false);
        return;
      }
      const img = new Image();
      img.onload = () => {
        const found = detect(img);
        const sx = img.naturalWidth / 1536;
        const sy = img.naturalHeight / 1024;
        const rects = found || FALLBACK[layout].map(([x, y, w, h]) => [x * sx, y * sy, w * sx, h * sy]);
        sheet = { url, width: img.naturalWidth, height: img.naturalHeight, rects: {}, detected: Boolean(found) };
        NAMES.forEach((name, i) => { sheet.rects[name] = rects[i]; });
        resolve(true);
      };
      img.onerror = () => {
        sheet = null;
        resolve(false);
      };
      img.src = url;
    });
  }

  // Square crop from a portrait panel, weighted towards the eyes.
  function paint(el, name) {
    if (!sheet) {
      el.style.backgroundImage = '';
      el.dataset.face = 'none';
      return;
    }
    const [x, y, w, h] = sheet.rects[name] || sheet.rects.neutral;
    const size = el.clientWidth || 72;
    const scale = size / w;
    const top = y + Math.max(0, h - w) * 0.3;
    el.style.backgroundImage = `url("${sheet.url}")`;
    el.style.backgroundSize = `${sheet.width * scale}px ${sheet.height * scale}px`;
    el.style.backgroundPosition = `${-x * scale}px ${-top * scale}px`;
    el.dataset.face = name;
  }

  return { NAMES, LABELS, load, paint, detected: () => Boolean(sheet && sheet.detected) };
})();

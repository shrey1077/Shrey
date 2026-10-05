'use strict';
// Brings Donna's pictures to life: breathing, a slow weight shift, head tilts, hair that sways, a
// nod while she talks, and a way of moving that follows her mood. A grid mesh is laid over the
// picture and gently deformed every frame with WebGL. Without WebGL, or with reduced motion
// turned on, the picture stays still.

const Motion = (() => {
  const COLS = 14;
  const ROWS = 28;
  const STYLES = {
    calm: { breathe: 1, sway: 1, hair: 1, speed: 1, bounce: 0, shake: 0, tilt: 0, droop: 0 },
    happy: { breathe: 1.1, sway: 1.35, hair: 1.3, speed: 1.15, bounce: 0.35, shake: 0, tilt: 0.4, droop: 0 },
    laughing: { breathe: 1.5, sway: 1.2, hair: 1.6, speed: 1.5, bounce: 1.4, shake: 0, tilt: 0.3, droop: 0 },
    angry: { breathe: 1.5, sway: 0.35, hair: 0.7, speed: 1.3, bounce: 0, shake: 0, tilt: 0, droop: 0 },
    furious: { breathe: 2, sway: 0.25, hair: 1.2, speed: 1.9, bounce: 0, shake: 1, tilt: 0, droop: 0 },
    sad: { breathe: 0.7, sway: 0.55, hair: 0.55, speed: 0.6, bounce: 0, shake: 0, tilt: 0.5, droop: 1 },
    thoughtful: { breathe: 0.8, sway: 0.7, hair: 0.8, speed: 0.75, bounce: 0, shake: 0, tilt: 1, droop: 0 },
  };
  const MOOD_STYLE = {
    happy: 'happy', playful: 'happy', adoring: 'happy', relaxed: 'happy', blissful: 'happy', laughing: 'laughing',
    angry: 'angry', cool: 'angry', furious: 'furious', crying: 'sad', sobbing: 'sad', sad: 'sad',
    thoughtful: 'thoughtful', cooling: 'thoughtful',
  };

  let canvas = null;
  let gl = null;
  let prog = null;
  let posBuf = null;
  let uvBuf = null;
  let tex = null;
  let count = 0;
  let pic = null; // { img, cutout, weights, aspect }
  let style = { ...STYLES.calm };
  let target = STYLES.calm;
  let talkUntil = 0;
  let raf = 0;
  let last = 0;
  const reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  const t0 = performance.now();

  const VS = 'attribute vec2 p; attribute vec2 uv; varying vec2 v; void main(){ v = uv; gl_Position = vec4(p, 0.0, 1.0); }';
  const FS = 'precision mediump float; varying vec2 v; uniform sampler2D t; void main(){ gl_FragColor = texture2D(t, v); }';

  function shader(type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    return s;
  }

  function init(el) {
    canvas = el;
    gl = canvas.getContext('webgl', { alpha: true, premultipliedAlpha: true, antialias: true });
    if (!gl) return false;
    prog = gl.createProgram();
    gl.attachShader(prog, shader(gl.VERTEX_SHADER, VS));
    gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      gl = null;
      return false;
    }
    gl.useProgram(prog);
    posBuf = gl.createBuffer();
    uvBuf = gl.createBuffer();
    const idx = [];
    for (let r = 0; r < ROWS; r += 1) {
      for (let c = 0; c < COLS; c += 1) {
        const a = r * (COLS + 1) + c;
        const b = a + 1;
        const d = a + COLS + 1;
        const e = d + 1;
        idx.push(a, b, d, b, e, d);
      }
    }
    count = idx.length;
    const ib = gl.createBuffer();
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ib);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(idx), gl.STATIC_DRAW);
    const uvs = [];
    for (let r = 0; r <= ROWS; r += 1) for (let c = 0; c <= COLS; c += 1) uvs.push(c / COLS, r / ROWS);
    gl.bindBuffer(gl.ARRAY_BUFFER, uvBuf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(uvs), gl.STATIC_DRAW);
    const uvLoc = gl.getAttribLocation(prog, 'uv');
    gl.enableVertexAttribArray(uvLoc);
    gl.vertexAttribPointer(uvLoc, 2, gl.FLOAT, false, 0, 0);
    tex = gl.createTexture();
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    return true;
  }

  // Where the head, chest and hair are, estimated from the picture's shape and colours.
  function analyse(img, cutout) {
    const aspect = img.naturalHeight / img.naturalWidth;
    const kind = aspect >= 2.2 ? 'full' : aspect >= 1.25 ? 'mid' : 'close';
    const shape = {
      full: { neck: 0.19, fade: 0.06, chest: 0.29, chestW: 0.07, pivot: 0.985 },
      mid: { neck: 0.34, fade: 0.1, chest: 0.5, chestW: 0.11, pivot: 1.25 },
      close: { neck: 0.66, fade: 0.2, chest: 0.92, chestW: 0.16, pivot: 1.6 },
    }[kind];
    const sw = (COLS + 1) * 4;
    const sh = (ROWS + 1) * 4;
    const c = document.createElement('canvas');
    c.width = sw;
    c.height = sh;
    const ctx = c.getContext('2d', { willReadFrequently: true });
    ctx.drawImage(img, 0, 0, sw, sh);
    const data = ctx.getImageData(0, 0, sw, sh).data;
    const copper = (i) => {
      const r = data[i] / 255;
      const g = data[i + 1] / 255;
      const b = data[i + 2] / 255;
      const a = data[i + 3] / 255;
      const max = Math.max(r, g, b);
      const min = Math.min(r, g, b);
      const s = max ? (max - min) / max : 0;
      // Her hair: saturated copper, darker than her skin.
      return a > 0.5 && r === max && g < r * 0.72 && b < g * 0.95 && s > 0.48 && max > 0.22 && max < 0.9 ? 1 : 0;
    };
    const weights = [];
    for (let r = 0; r <= ROWS; r += 1) {
      for (let col = 0; col <= COLS; col += 1) {
        const u = col / COLS;
        const v = r / ROWS;
        let hair = 0;
        for (let dy = 0; dy < 4; dy += 1) {
          for (let dx = 0; dx < 4; dx += 1) {
            const x = Math.min(sw - 1, col * 4 + dx);
            const y = Math.min(sh - 1, r * 4 + dy);
            hair += copper((y * sw + x) * 4);
          }
        }
        hair /= 16;
        if (!cutout && Math.abs(u - 0.5) > 0.38) hair = 0; // leave the background alone
        const head = v <= shape.neck ? 1 : Math.max(0, 1 - (v - shape.neck) / shape.fade);
        const chest = Math.exp(-(((v - shape.chest) / shape.chestW) ** 2));
        const tips = Math.min(1, Math.max(0.25, (v - 0.02) / 0.4));
        weights.push({ u, v, head, chest, hair: hair * tips, planted: cutout && kind === 'full' && v > 0.95 ? 0 : 1 });
      }
    }
    return { kind, shape, weights };
  }

  function show(url, opts = {}) {
    if (!gl) return Promise.resolve(false);
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => {
        gl.bindTexture(gl.TEXTURE_2D, tex);
        gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        pic = { img, cutout: Boolean(opts.cutout), ...analyse(img, Boolean(opts.cutout)) };
        draw(performance.now());
        if (!raf && !reduced) raf = requestAnimationFrame(loop);
        resolve(true);
      };
      img.onerror = () => resolve(false);
      img.src = url;
    });
  }

  function mood(emotion) {
    target = STYLES[MOOD_STYLE[emotion] || 'calm'];
  }

  function talk(ms) {
    talkUntil = performance.now() + Math.min(4000, Math.max(600, ms));
  }

  function fit() {
    const dpr = window.devicePixelRatio || 1;
    const w = Math.round(canvas.clientWidth * dpr);
    const h = Math.round(canvas.clientHeight * dpr);
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    gl.viewport(0, 0, w, h);
    const iw = pic.img.naturalWidth;
    const ih = pic.img.naturalHeight;
    // Cut-out figures stand on the floor (contain); framed pictures fill the frame (cover).
    const scale = pic.cutout ? Math.min(w / iw, h / ih) : Math.max(w / iw, h / ih);
    const rw = iw * scale;
    const rh = ih * scale;
    const x = (w - rw) / 2;
    const y = pic.cutout ? h - rh : (h - rh) * 0.18;
    return { w, h, x, y, rw, rh };
  }

  function draw(now) {
    if (!gl || !pic || !canvas.clientWidth) return;
    const k = 0.06; // ease towards the target mood
    for (const key of Object.keys(style)) style[key] += (target[key] - style[key]) * k;
    const s = style;
    const t = (now - t0) / 1000;
    const ph = t * s.speed;
    const TAU = Math.PI * 2;
    const breath = Math.sin((ph * TAU) / 4.2);
    const sway = Math.sin((ph * TAU) / 8) * 0.006 * s.sway;
    const tilt = Math.sin((ph * TAU) / 5.6 + 1.3) * 0.02 * s.sway + 0.02 * s.tilt;
    const talking = now < talkUntil;
    const nod = talking ? Math.sin(t * TAU * 2.6) * 0.008 : 0;
    const bounce = -Math.abs(Math.sin(t * TAU * 2)) * 0.007 * s.bounce;
    const shake = Math.sin(t * TAU * 9) * 0.012 * s.shake;
    const droop = 0.008 * s.droop;
    const r = fit();
    const { shape } = pic;
    const neckX = r.x + 0.5 * r.rw;
    const neckY = r.y + shape.neck * r.rh;
    const pivX = r.x + 0.5 * r.rw;
    const pivY = r.y + shape.pivot * r.rh;
    const pos = new Float32Array(pic.weights.length * 2);
    pic.weights.forEach((wt, i) => {
      let x = r.x + wt.u * r.rw;
      let y = r.y + wt.v * r.rh;
      // breathing: the chest rises, the head rides on it
      y -= (wt.chest * 0.004 + wt.head * 0.003) * breath * s.breathe * r.rh;
      // head tilt, shake and nod around the neck
      const a = (tilt + shake) * wt.head;
      if (a) {
        const dx = x - neckX;
        const dy = y - neckY;
        x = neckX + dx * Math.cos(a) - dy * Math.sin(a);
        y = neckY + dx * Math.sin(a) + dy * Math.cos(a);
      }
      y += (nod + droop) * wt.head * r.rh;
      // weight shift around the feet (or below the frame)
      const b = sway * (1 - wt.v) * wt.planted;
      if (b) {
        const dx = x - pivX;
        const dy = y - pivY;
        x = pivX + dx * Math.cos(b) - dy * Math.sin(b);
        y = pivY + dx * Math.sin(b) + dy * Math.cos(b);
      }
      y += bounce * (1 - wt.v) * wt.planted * r.rh;
      // hair moves on its own, more at the tips
      x += wt.hair * Math.sin((ph * TAU) / 3.4 + wt.v * 6 + wt.u * 2) * 0.006 * s.hair * r.rh;
      pos[i * 2] = (x / r.w) * 2 - 1;
      pos[i * 2 + 1] = 1 - (y / r.h) * 2;
    });
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.bindBuffer(gl.ARRAY_BUFFER, posBuf);
    gl.bufferData(gl.ARRAY_BUFFER, pos, gl.DYNAMIC_DRAW);
    const loc = gl.getAttribLocation(prog, 'p');
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.drawElements(gl.TRIANGLES, count, gl.UNSIGNED_SHORT, 0);
  }

  function loop(now) {
    raf = requestAnimationFrame(loop);
    if (document.hidden || now - last < 33) return; // about 30 frames a second, paused when hidden
    last = now;
    draw(now);
  }

  return { init, show, mood, talk, enabled: () => Boolean(gl) };
})();

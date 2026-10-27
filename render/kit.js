/* Avatar Studio composition kit: builds the whole video from window.SB (the resolved storyboard). */
(function () {
  const { clamp, lerp, EASE, Anim, rng } = window.AVS;
  const SB = window.SB;
  const Q = new URLSearchParams(location.search);
  const MODE = Q.get('mode') || 'video';
  const W = +Q.get('w') || SB.meta.width;
  const H = +Q.get('h') || SB.meta.height;
  const FPS = SB.meta.fps;
  const DIR = SB.meta.dir || 'rtl';
  const RTL = DIR === 'rtl';
  const stage = document.getElementById('stage');
  const px = (v) => v + 'px';
  const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; };
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  const A = new Anim();
  const fits = [];      // text fitting jobs, run once fonts are ready
  const preps = [];     // jobs that need layout (svg path lengths)
  const decodes = [];   // images to decode before the first frame

  // ------------------------------------------------------------------ world
  const WD = SB.world;
  stage.style.width = px(W); stage.style.height = px(H); stage.setAttribute('dir', DIR);
  const rs = stage.style;
  rs.setProperty('--bg', WD.palette.bg); rs.setProperty('--ink', WD.palette.ink); rs.setProperty('--paper', WD.palette.paper);
  rs.setProperty('--accent', WD.palette.accent); rs.setProperty('--accent2', WD.palette.accent2);
  rs.setProperty('--font-display', `'${WD.type.display}', 'Heebo', sans-serif`);
  rs.setProperty('--font-body', `'${WD.type.body}', 'Heebo', sans-serif`);
  rs.setProperty('--disp-weight', WD.type.weight); rs.setProperty('--track', WD.type.tracking || '0em');

  const G = {};
  ['plates', 'back', 'avatar', 'front', 'caps', 'fx'].forEach((id) => { G[id] = el('div', 'grp'); G[id].id = id; stage.appendChild(G[id]); });

  // -------------------------------------------------------------- positions
  const POS = { top: [0.5, 0.13], upper: [0.5, 0.25], mid: [0.5, 0.4], center: [0.5, 0.5], lower: [0.5, 0.6], low: [0.5, 0.72], bottom: [0.5, 0.86] };
  function posOf(L, def) {
    const p = L.pos !== undefined ? L.pos : def || 'mid';
    const a = typeof p === 'string' ? POS[p] || POS.mid : p;
    return [a[0] * W, a[1] * H];
  }
  function mkPos(L, def, wDef) {
    const [x, y] = posOf(L, def);
    const d = el('div', 'pos');
    d.style.left = px(x); d.style.top = px(y); d.style.width = px((L.w || wDef || 0.88) * W);
    if (L.h) d.style.height = px(L.h * H);
    return d;
  }
  // timing helpers: at/until are absolute seconds (resolved by the build step)
  const tIn = (L, S) => (L.at !== undefined ? L.at : S.start + 0.3);
  const tOut = (L, S) => (L.until !== undefined ? L.until : S.end);
  const settle = (L, dur) => (L.settle ? -dur : 0);

  function showWin(wrapEls, t0, t1) { [].concat(wrapEls).forEach((e) => A.show(e, t0 - 0.05, t1 + 0.05)); }
  function exitFade(L, S, inner) {
    if (L.until !== undefined && L.until < S.end - 0.12) A.tween(inner, L.until - 0.15, 0.15, { opacity: [1, 0] }, 'inQuad');
  }
  function words(box, text) {
    const spans = [];
    String(text).split('\n').forEach((ln, li) => {
      if (li) box.appendChild(document.createElement('br'));
      ln.split('*').forEach((seg, si) => {
        seg.split(/\s+/).filter(Boolean).forEach((tok) => {
          const w = el('span', 'w' + (si % 2 ? ' em' : ''));
          w.textContent = tok;
          box.appendChild(w); box.appendChild(document.createTextNode(' '));
          spans.push(w);
        });
      });
    });
    return spans;
  }
  function addFit(e, opt) { fits.push(Object.assign({ el: e }, opt)); }

  // ----------------------------------------------------------------- layers
  const build = {};

  build.headline = (L, S, c) => {
    const wrap = mkPos(L, 'upper', 0.9);
    const style = L.style || 'plain';
    const inner = el('div', 'in');
    inner.__base = { rotate: L.rot || 0 };
    const box = el('div', `hl hl-${style} ${L.color || ''} ${L.mock ? 'mock' : ''}`.trim());
    box.style.fontSize = px(L.size || 150);
    if (L.align === 'start') box.style.textAlign = 'start';
    const sp = words(box, L.text);
    if (L.emphasis) { const em = [].concat(L.emphasis).map(String); sp.forEach((s, i) => { if (em.includes(String(i)) || em.includes(s.textContent)) s.classList.add('em'); }); }
    inner.appendChild(box); wrap.appendChild(inner);
    if (L.mock) {
      const m = L.mock;
      inner.__base = { rotate: m.rotateZ || L.rot || 0, rotateX: m.rotateX || 0, rotateY: m.rotateY || 0 };
      if (m.blend === false) box.classList.remove('mock'); if (m.opacity !== undefined) box.style.opacity = m.opacity;
    }
    addFit(box, { w: (L.w || 0.9) * W, h: (L.maxh || 0.34) * H, min: 36, max: L.size || 150 });
    const t0 = tIn(L, S), t1 = tOut(L, S), an = L.anim || 'pop-words';
    const d0 = t0 + settle(L, 0.5);
    if (an === 'pop-words' || an === 'rise' || an === 'type') {
      sp.forEach((s, i) => {
        const d = d0 + i * (an === 'type' ? 0.11 : 0.075);
        if (an === 'rise') A.tween(s, d, 0.45, { yp: [90, 0], opacity: [0, 1] }, 'outCubic');
        else if (an === 'type') A.set(s, d, { opacity: [0, 1] });
        else A.tween(s, d, 0.34, { scale: [0.55, 1], yp: [30, 0], opacity: [0, 1] }, 'outBackSoft');
      });
    } else if (an === 'slam') {
      A.tween(inner, d0, 0.3, { scale: [1.8, 1], opacity: [0, 1] }, 'outExpo');
      A.tween(inner, d0 + 0.3, 0.2, { rotate: [(L.rot || 0) + 2.5, L.rot || 0] }, 'outElastic');
    } else if (an === 'wipe') {
      inner.__base.clip = [0, 0, 0, 0];
      A.tween(inner, d0, 0.5, { clip: RTL ? [[0, 0, 0, 100], [0, 0, 0, 0]] : [[0, 100, 0, 0], [0, 0, 0, 0]] }, 'inOutCubic');
    } else { A.tween(inner, d0, 0.4, { opacity: [0, 1] }, 'outCubic'); }
    if (an !== 'pop-words' && an !== 'rise' && an !== 'type') { /* inner handles opacity */ }
    if (style === 'stamp') A.tween(inner, d0, 0.34, { scale: [2.2, 1], opacity: [0, 0.94], rotate: [(L.rot || -6) - 6, L.rot || -6] }, 'outExpo');
    exitFade(L, S, inner);
    (L.behind ? c.back : c.front).appendChild(wrap);
    showWin(wrap, d0, t1);
  };

  build.stamp = (L, S, c) => {
    build.headline(Object.assign({ style: 'stamp', size: L.size || 120, rot: L.rot !== undefined ? L.rot : -7, anim: 'none', w: L.w || 0.7, pos: L.pos || 'mid' }, L), S, c);
  };

  build.badge = (L, S, c) => {
    const wrap = mkPos(L, 'upper', 0.2); const inner = el('div', 'badge', esc(L.text)); wrap.appendChild(inner);
    if (L.color === 'ink') { inner.style.background = 'var(--ink)'; }
    const t0 = tIn(L, S);
    A.tween(inner, t0 + settle(L, 0.4), 0.4, { scale: [0, 1], rotate: [-25, 0] }, 'outBackHard');
    exitFade(L, S, inner);
    c.front.appendChild(wrap); showWin(wrap, t0 + settle(L, 0.4), tOut(L, S));
  };

  function svgLayer(c, behind) {
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('class', 'draw'); s.setAttribute('viewBox', `0 0 ${W} ${H}`);
    (behind ? c.back : c.front).appendChild(s);
    return s;
  }
  function svgPath(svg, d, color, width, shadow) {
    const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', d); p.setAttribute('stroke', color); p.setAttribute('stroke-width', width);
    if (shadow !== false) p.__filter = 'drop-shadow(0 4px 8px rgba(0,0,0,0.35))';
    svg.appendChild(p);
    preps.push(() => { p.__len = p.getTotalLength(); p.style.strokeDasharray = p.__len; p.style.strokeDashoffset = p.__len; });
    return p;
  }
  const col = (c, d) => (c === 'ink' ? 'var(--ink)' : c === 'paper' ? 'var(--paper)' : c === 'accent2' ? 'var(--accent2)' : c && c[0] === '#' ? c : d || 'var(--accent)');

  build.circle = (L, S, c) => {
    const [rx, ry, rw, rh] = L.rect; const cx = (rx + rw / 2) * W, cy = (ry + rh / 2) * H, a = (rw / 2) * W * 1.1, b = (rh / 2) * H * 1.35;
    const r = rng(Math.round(cx * 7 + cy));
    const pts = [];
    const N = 28, start = -2.4 + r() * 0.4;
    for (let i = 0; i <= N + 3; i++) {
      const th = start + (i / N) * Math.PI * 2 * 1.04;
      const k = 1 + 0.05 * Math.sin(i * 0.9 + r()) + i / (N * 40);
      pts.push([cx + Math.cos(th) * a * k, cy + Math.sin(th) * b * k]);
    }
    let d = `M ${pts[0][0].toFixed(1)} ${pts[0][1].toFixed(1)}`;
    for (let i = 1; i < pts.length - 1; i++) { const mx = (pts[i][0] + pts[i + 1][0]) / 2, my = (pts[i][1] + pts[i + 1][1]) / 2; d += ` Q ${pts[i][0].toFixed(1)} ${pts[i][1].toFixed(1)} ${mx.toFixed(1)} ${my.toFixed(1)}`; }
    const svg = svgLayer(c, L.behind); const p = svgPath(svg, d, col(L.color), L.width || 12);
    const t0 = tIn(L, S) + settle(L, 0.6); A.tween(p, t0, L.dur || 0.6, { dash: [0, 1] }, 'inOutCubic');
    exitFade(L, S, p); showWin(svg, t0, tOut(L, S));
  };

  build.underline = (L, S, c) => {
    const [rx, ry, rw, rh] = L.rect; const y = (L.strike ? ry + rh / 2 : ry + rh) * H, x0 = rx * W, x1 = (rx + rw) * W;
    const d = `M ${x0} ${y} Q ${(x0 + x1) / 2} ${y + 14} ${x1} ${y - 6}`;
    const svg = svgLayer(c, L.behind); const p = svgPath(svg, d, col(L.color), L.width || 14);
    const t0 = tIn(L, S) + settle(L, 0.4); A.tween(p, t0, L.dur || 0.4, { dash: [0, 1] }, 'outCubic');
    exitFade(L, S, p); showWin(svg, t0, tOut(L, S));
  };
  build.strike = (L, S, c) => build.underline(Object.assign({ strike: true }, L), S, c);

  build.arrow = (L, S, c) => {
    const [x0, y0] = [L.from[0] * W, L.from[1] * H], [x1, y1] = [L.to[0] * W, L.to[1] * H];
    const k = L.curve === undefined ? 0.18 : L.curve; const mx = (x0 + x1) / 2 - (y1 - y0) * k, my = (y0 + y1) / 2 + (x1 - x0) * k;
    const ang = Math.atan2(y1 - my, x1 - mx), hl = 56;
    const head = (s) => `M ${x1} ${y1} L ${x1 - Math.cos(ang + s) * hl} ${y1 - Math.sin(ang + s) * hl}`;
    const svg = svgLayer(c, L.behind); const w = L.width || 14;
    const p = svgPath(svg, `M ${x0} ${y0} Q ${mx} ${my} ${x1} ${y1}`, col(L.color), w);
    const h1 = svgPath(svg, head(0.5), col(L.color), w), h2 = svgPath(svg, head(-0.5), col(L.color), w);
    const t0 = tIn(L, S) + settle(L, 0.6); A.tween(p, t0, 0.45, { dash: [0, 1] }, 'inOutCubic');
    A.tween(h1, t0 + 0.4, 0.14, { dash: [0, 1] }, 'outCubic'); A.tween(h2, t0 + 0.4, 0.14, { dash: [0, 1] }, 'outCubic');
    showWin(svg, t0, tOut(L, S));
  };

  build.counter = (L, S, c) => {
    const wrap = mkPos(L, 'mid', 0.9); const inner = el('div', 'in'); inner.__base = { rotate: L.rot || 0 };
    const box = el('div', 'counter'); box.style.fontSize = px(L.size || 280);
    const num = el('span', 'n'); box.appendChild(num);
    if (L.label) box.appendChild(el('small', '', esc(L.label)));
    inner.appendChild(box); wrap.appendChild(inner);
    const from = L.from || 0, to = L.to, dec = L.decimals || 0, t0 = tIn(L, S) + settle(L, 1), dur = L.dur || 1.1;
    const fmt = (v) => (L.prefix || '') + v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + (L.suffix || '');
    A.fn(t0, t0 + dur, (u) => { num.textContent = fmt(lerp(from, to, u)); }, 'outExpo');
    A.tween(inner, t0, 0.3, { scale: [0.8, 1], opacity: [0, 1] }, 'outBackSoft');
    addFit(box, { w: (L.w || 0.9) * W, h: 0.4 * H, min: 60, max: L.size || 280 });
    exitFade(L, S, inner); (L.behind ? c.back : c.front).appendChild(wrap); showWin(wrap, t0, tOut(L, S));
  };

  function enterFx(a, inner, kind, t0, rot) {
    const r = rot || 0;
    switch (kind) {
      case 'rise': a.tween(inner, t0, 0.55, { y: [300, 0], opacity: [0, 1] }, 'outCubic'); break;
      case 'drop': a.tween(inner, t0, 0.6, { y: [-H * 0.5, 0], opacity: [0, 1] }, 'outBackSoft'); break;
      case 'slide-left': a.tween(inner, t0, 0.55, { x: [-W, 0], opacity: [0, 1] }, 'outExpo'); break;
      case 'slide-right': a.tween(inner, t0, 0.55, { x: [W, 0], opacity: [0, 1] }, 'outExpo'); break;
      case 'tilt-in': a.tween(inner, t0, 0.6, { y: [220, 0], rotate: [r - 14, r], opacity: [0, 1] }, 'outBack'); break;
      case 'flip': a.tween(inner, t0, 0.6, { rotateY: [90, 0], opacity: [0, 1] }, 'outCubic'); break;
      case 'cut': a.set(inner, t0, { opacity: [0, 1] }); break;
      default: a.tween(inner, t0, 0.4, { scale: [0.6, 1], opacity: [0, 1] }, 'outBack');
    }
  }
  function idle(inner, t0, t1, amp) {
    const a = amp === undefined ? 7 : amp;
    A.fn(t0, t1, (u, t) => { inner.style.translate = `${(Math.sin(t * 1.3) * a * 0.5).toFixed(2)}px ${(Math.sin(t * 1.9) * a).toFixed(2)}px`; });
  }

  build.card = (L, S, c) => {
    const wrap = mkPos(L, 'center', 0.78); const inner = el('div', 'in'); inner.__base = { rotate: L.rot || 0 };
    const card = el('div', 'card' + (L.text || L.html ? ' text' : ''));
    if (L.src) { const im = el('img'); im.src = L.src; card.appendChild(im); decodes.push(im); }
    else if (L.html) card.innerHTML = L.html; else card.textContent = L.text || '';
    if (L.radius !== undefined) card.style.borderRadius = px(L.radius);
    if (L.bg) card.style.background = col(L.bg); if (L.textColor) card.style.color = col(L.textColor);
    inner.appendChild(card); wrap.appendChild(inner);
    const t0 = tIn(L, S) + settle(L, 0.6); enterFx(A, inner, L.enter || 'pop', t0, L.rot);
    if (L.idle !== false) idle(inner, t0, tOut(L, S), 6);
    exitFade(L, S, inner); (L.behind ? c.back : c.front).appendChild(wrap); showWin(wrap, t0, tOut(L, S));
  };

  build.sticker = (L, S, c) => {
    const wrap = mkPos(L, 'center', 0.5); const inner = el('div', 'in sticker'); inner.__base = { rotate: L.rot || 0 };
    const im = el('img'); im.src = L.src; inner.appendChild(im); wrap.appendChild(inner); decodes.push(im);
    const t0 = tIn(L, S) + settle(L, 0.6); enterFx(A, inner, L.enter || 'pop', t0, L.rot);
    if (L.idle !== false) idle(inner, t0, tOut(L, S), 9);
    exitFade(L, S, inner); (L.behind ? c.back : c.front).appendChild(wrap); showWin(wrap, t0, tOut(L, S));
  };

  build.list = (L, S, c) => {
    const wrap = mkPos(L, 'center', 0.86); const inner = el('div', 'in'); const list = el('div', 'list'); inner.appendChild(list); wrap.appendChild(inner);
    (L.items || []).forEach((it, i) => {
      const row = el('div', 'item', `<i>${L.numbered === false ? '✓' : i + 1}</i><span>${esc(it.text)}</span>`);
      list.appendChild(row);
      const t0 = it.at !== undefined ? it.at : tIn(L, S) + i * 0.6;
      A.tween(row, t0, 0.5, { x: [RTL ? 600 : -600, 0], opacity: [0, 1] }, 'outExpo');
    });
    exitFade(L, S, inner); c.front.appendChild(wrap); showWin(wrap, tIn(L, S), tOut(L, S));
  };

  build.quote = (L, S, c) => {
    const wrap = mkPos(L, 'mid', 0.84); const inner = el('div', 'in'); inner.__base = {};
    const q = el('div', 'quote', `<span class="mark">“</span>${esc(L.text).replace(/\n/g, '<br>')}${L.who ? `<small>${esc(L.who)}</small>` : ''}`);
    q.style.fontSize = px(L.size || 88); inner.appendChild(q); wrap.appendChild(inner);
    addFit(q, { w: (L.w || 0.84) * W, h: 0.4 * H, min: 40, max: L.size || 88 });
    const t0 = tIn(L, S) + settle(L, 0.6); A.tween(inner, t0, 0.6, { yp: [8, 0], opacity: [0, 1] }, 'outCubic');
    exitFade(L, S, inner); c.front.appendChild(wrap); showWin(wrap, t0, tOut(L, S));
  };

  build.lower = (L, S, c) => {
    const wrap = mkPos(L, [0.5, 0.58], 0.8); wrap.style.justifyContent = 'flex-start'; const inner = el('div', 'in lower', `<b>${esc(L.title)}</b>${L.sub ? `<span>${esc(L.sub)}</span>` : ''}`);
    wrap.appendChild(inner); const t0 = tIn(L, S) + settle(L, 0.6);
    A.tween(inner, t0, 0.55, { x: [RTL ? 700 : -700, 0], opacity: [0, 1] }, 'outExpo'); exitFade(L, S, inner);
    c.front.appendChild(wrap); showWin(wrap, t0, tOut(L, S));
  };

  build.bars = (L, S, c) => {
    const wrap = mkPos(L, 'mid', 0.84); wrap.style.height = px((L.h || 0.3) * H); const inner = el('div', 'in bars'); inner.style.height = '100%'; wrap.appendChild(inner);
    const max = Math.max(...L.values.map((v) => v.value));
    const t0 = tIn(L, S) + settle(L, 1);
    L.values.forEach((v, i) => {
      const b = el('div', 'b'); const val = el('div', 'val', esc((L.prefix || '') + v.value + (L.suffix || ''))); const bar = el('div', 'bar' + (v.hot ? ' hot' : '')); const lbl = el('div', 'lbl', esc(v.label || ''));
      b.appendChild(val); b.appendChild(bar); b.appendChild(lbl); inner.appendChild(b);
      bar.style.height = '0px'; const target = (v.value / max) * (L.h || 0.3) * H * 0.62;
      A.fn(t0 + i * 0.18, t0 + i * 0.18 + 0.7, (u) => { bar.style.height = px(target * u); val.style.opacity = u > 0.05 ? 1 : 0; }, 'outBackSoft');
    });
    exitFade(L, S, inner); c.front.appendChild(wrap); showWin(wrap, t0, tOut(L, S));
  };

  build.ticker = (L, S, c) => {
    const wrap = mkPos(L, [0.5, 0.9], 1); const inner = el('div', 'in ticker'); const sp = el('span', '', esc((L.text + '   •   ').repeat(8))); inner.appendChild(sp); wrap.appendChild(inner);
    const t0 = tIn(L, S); A.fn(t0, tOut(L, S), (u, t) => { sp.style.transform = `translateX(${(-((t - t0) * (L.speed || 220)) % 1800).toFixed(1)}px)`; });
    A.tween(inner, t0, 0.3, { yp: [100, 0] }, 'outCubic'); c.front.appendChild(wrap); showWin(wrap, t0, tOut(L, S));
  };

  build.compare = (L, S, c) => {
    const wrap = mkPos(L, 'center', 0.88); wrap.style.height = px((L.h || 0.34) * H); const inner = el('div', 'in compare'); inner.style.height = '100%'; wrap.appendChild(inner);
    [['left', L.left], ['right', L.right]].forEach(([side, v]) => {
      const h = el('div', 'half'); h.style[side] = '0'; if (v.bg) h.style.background = col(v.bg);
      if (v.src) { const im = el('img'); im.src = v.src; h.appendChild(im); decodes.push(im); }
      h.appendChild(el('b', '', esc(v.label || ''))); inner.appendChild(h);
      const t0 = tIn(L, S); A.tween(h, t0 + (side === 'left' ? 0 : 0.25), 0.5, { x: [side === 'left' ? -500 : 500, 0], opacity: [0, 1] }, 'outExpo');
    });
    inner.appendChild(el('div', 'div')); const t0 = tIn(L, S) + settle(L, 0.6);
    A.tween(inner, t0, 0.3, { scale: [0.9, 1], opacity: [0, 1] }, 'outCubic'); exitFade(L, S, inner); c.front.appendChild(wrap); showWin(wrap, t0, tOut(L, S));
  };

  build.shape = (L, S, c) => {
    const [rx, ry, rw, rh] = L.rect; const e = el('div'); const s = e.style; s.position = 'absolute'; s.left = px(rx * W); s.top = px(ry * H); s.width = px(rw * W); s.height = px(rh * H);
    s.background = col(L.color, 'var(--accent)'); s.borderRadius = L.kind === 'circle' ? '50%' : px(L.radius || 0); s.opacity = L.opacity === undefined ? 1 : L.opacity;
    e.__base = { rotate: L.rot || 0 };
    const t0 = tIn(L, S) + settle(L, 0.4);
    A.tween(e, t0, 0.4, L.anim === 'grow-x' ? { scaleX: [0, 1] } : L.anim === 'grow-y' ? { scaleY: [0, 1] } : { opacity: [0, L.opacity === undefined ? 1 : L.opacity] }, 'outCubic');
    e.style.transformOrigin = RTL ? 'right center' : 'left center';
    (L.behind ? c.back : c.front).appendChild(e); showWin(e, t0, tOut(L, S));
  };

  build.flash = (L, S, c) => {
    const e = el('div'); e.style.cssText = 'position:absolute;inset:0;'; e.style.background = col(L.color, 'var(--paper)'); e.__base = { opacity: 0 }; const t0 = tIn(L, S);
    A.tween(e, t0, 0.04, { opacity: [0, L.strength || 0.85] }, 'linear'); A.tween(e, t0 + 0.04, L.dur || 0.28, { opacity: [L.strength || 0.85, 0] }, 'outCubic');
    c.front.appendChild(e); showWin(e, t0, t0 + (L.dur || 0.28) + 0.1);
  };

  build.particles = (L, S, c) => {
    const kind = L.kind || 'dust', n = L.count || 28, r = rng(L.seed || 11), t0 = tIn(L, S), t1 = tOut(L, S);
    const box = el('div'); box.style.cssText = 'position:absolute;inset:0;overflow:hidden;';
    for (let i = 0; i < n; i++) {
      const p = el('div', 'particle'); const sz = kind === 'confetti' ? 14 + r() * 14 : kind === 'sparks' ? 3 + r() * 5 : 4 + r() * 10;
      p.style.width = px(sz); p.style.height = px(kind === 'confetti' ? sz * 1.8 : sz);
      p.style.background = kind === 'confetti' ? [col('accent'), col('accent2'), col('paper')][i % 3] : kind === 'sparks' ? col('accent2') : 'rgba(255,255,255,0.7)';
      if (kind === 'dust') p.style.filter = 'blur(1.5px)'; if (kind === 'sparks') p.style.boxShadow = '0 0 14px var(--accent2)';
      const x0 = r() * W, y0 = r() * H, vx = (r() - 0.5) * (kind === 'dust' ? 40 : 220), vy = kind === 'confetti' ? 260 + r() * 300 : kind === 'sparks' ? -(120 + r() * 280) : -(10 + r() * 50);
      const ph = r() * 6.28, life = 1.2 + r() * 1.6, off = r() * (t1 - t0);
      A.fn(t0, t1, (u, t) => {
        const tt = (t - t0 + off) % life, k = tt / life;
        p.style.transform = `translate(${(x0 + vx * tt + Math.sin(ph + tt * 2) * 14).toFixed(1)}px, ${(y0 + vy * tt + (kind === 'sparks' ? 300 * tt * tt : 0)).toFixed(1)}px) rotate(${(ph * 57 + tt * 360).toFixed(0)}deg)`;
        p.style.opacity = (kind === 'dust' ? 0.55 : 1) * Math.sin(Math.PI * k);
      });
      box.appendChild(p);
    }
    (L.behind ? c.back : c.front).appendChild(box); showWin(box, t0, t1);
  };

  build.lightsweep = (L, S, c) => {
    const e = el('div', 'sweep'); e.style.background = `linear-gradient(90deg, transparent, ${col(L.color, 'rgba(255,240,210,0.55)')}, transparent)`; e.style.transform = `skewX(${L.angle || -18}deg)`;
    const t0 = tIn(L, S); const d = L.dur || 1.1;
    A.fn(t0, t0 + d, (u) => { e.style.left = px(lerp(-0.3 * W, 1.1 * W, u)); e.style.opacity = Math.sin(Math.PI * u) * (L.strength || 0.8); }, 'inOutSine');
    c.front.appendChild(e); showWin(e, t0, t0 + d);
  };

  build.html = (L, S, c) => {
    const wrap = mkPos(L, 'center', 0.8); const inner = el('div', 'in', L.html || ''); wrap.appendChild(inner);
    if (L.css) { const st = document.createElement('style'); st.textContent = L.css; document.head.appendChild(st); }
    const t0 = tIn(L, S); const t1 = tOut(L, S);
    if (L.js) { try { new Function('el', 'api', L.js)(inner, { A, W, H, t0, t1, S, AVS: window.AVS, RTL, px, el }); } catch (e) { console.error('html layer js:', e); } }
    else A.tween(inner, t0, 0.4, { opacity: [0, 1] }, 'outCubic');
    exitFade(L, S, inner); (L.behind ? c.back : c.front).appendChild(wrap); showWin(wrap, t0, t1);
  };

  // ------------------------------------------------------------ transitions
  // each returns {inFrom, outTo} offsets so overlap windows are right
  function band(n, u, fromRight) {
    const h = H / n; let d = '';
    for (let i = 0; i < n; i++) {
      const k = clamp(u * 1.5 - (i / n) * 0.5); const w = W * k; const x = (fromRight ^ (i % 2)) ? W - w : 0;
      d += `M ${x} ${i * h} h ${w} v ${h + 1} h ${-w} z `;
    }
    return `path('${d}')`;
  }
  const TR = {
    cut() {},
    'soft-push'(o, i, t, d) {
      A.tween(i.plate, t, d, { yp: [7, 0], opacity: [0, 1] }, 'outCubic');
      i.layers.forEach((e) => A.tween(e, t + d * 0.25, d * 0.75, { opacity: [0, 1] }, 'outCubic'));
      A.tween(o.plate, t, d, { scale: [1, 1.05] }, 'inCubic');
      o.layers.forEach((e) => A.tween(e, t, d * 0.6, { opacity: [1, 0] }, 'inQuad'));
    },
    'whip-pan'(o, i, t, d) {
      const s = RTL ? -1 : 1;
      [i.plate].concat(i.layers).forEach((e) => { A.tween(e, t, d, { x: [s * W * 0.95, 0] }, 'inOutExpo'); A.tween(e, t, d * 0.5, { blur: [0, 16] }, 'outQuad'); A.tween(e, t + d * 0.5, d * 0.5, { blur: [16, 0] }, 'inQuad'); });
      [o.plate].concat(o.layers).forEach((e) => { A.tween(e, t, d, { x: [0, -s * W * 0.95] }, 'inOutExpo'); A.tween(e, t, d * 0.5, { blur: [0, 16] }, 'outQuad'); });
    },
    iris(o, i, t, d, S) {
      const fx = (S.plate && S.plate.focus ? S.plate.focus[0] : 0.5) * 100, fy = (S.plate && S.plate.focus ? S.plate.focus[1] : 0.45) * 100;
      A.tween(i.plate, t, d, { iris: [[0, fx, fy], [150, fx, fy]] }, 'inOutCubic');
      i.layers.forEach((e) => A.tween(e, t + d * 0.5, d * 0.5, { opacity: [0, 1] }, 'outCubic'));
      o.layers.forEach((e) => A.tween(e, t, d * 0.4, { opacity: [1, 0] }, 'inQuad'));
    },
    'slide-wipe'(o, i, t, d) {
      const from = RTL ? [[0, 0, 0, 100], [0, 0, 0, 0]] : [[0, 100, 0, 0], [0, 0, 0, 0]];
      A.tween(i.plate, t, d, { clip: from }, 'inOutCubic');
      i.layers.forEach((e) => A.tween(e, t, d, { clip: from }, 'inOutCubic'));
      const bar = el('div', 'fxbar'); G.fx.appendChild(bar); bar.__base = { opacity: 0 };
      A.tween(bar, t, d, { x: RTL ? [W, -14] : [-14, W], opacity: [1, 1] }, 'inOutCubic'); A.set(bar, t + d, { opacity: [0, 0] }); A.show(bar, t - 0.02, t + d + 0.05);
      o.layers.forEach((e) => A.tween(e, t, d * 0.7, { opacity: [1, 0] }, 'inQuad'));
    },
    'dip-flash'(o, i, t, d, S, X) {
      const f = X.flash; const k = 0.42;
      A.tween(f, t, d * k, { opacity: [0, 1] }, 'outCubic'); A.tween(f, t + d * k, d * (1 - k), { opacity: [1, 0] }, 'inCubic');
      X.inFrom = t + d * k; X.outTo = t + d * k;
      i.layers.forEach((e) => A.tween(e, t + d * k, d * 0.5, { opacity: [0, 1] }, 'outCubic'));
    },
    'zoom-through'(o, i, t, d) {
      A.tween(o.plate, t, d, { scale: [1, 1.9], blur: [0, 14], opacity: [1, 0] }, 'inCubic');
      A.tween(i.plate, t, d, { scale: [0.72, 1], blur: [14, 0], opacity: [0, 1] }, 'outCubic');
      o.layers.forEach((e) => A.tween(e, t, d * 0.5, { opacity: [1, 0], scale: [1, 1.4] }, 'inQuad'));
      i.layers.forEach((e) => A.tween(e, t + d * 0.4, d * 0.6, { opacity: [0, 1] }, 'outCubic'));
    },
    'paper-turn'(o, i, t, d) {
      const sk = 40;
      A.fn(t, t + d, (u) => {
        const b = (1 - u) * (100 + sk);
        const p = RTL ? `polygon(${b}% 0, 100% 0, 100% 100%, ${b - sk}% 100%)` : `polygon(0 0, ${100 - b}% 0, ${100 - b + sk}% 100%, 0 100%)`;
        const cp = u >= 1 ? 'none' : u <= 0 ? 'polygon(0 0,0 0,0 0)' : p;
        i.plate.style.clipPath = cp; i.layers.forEach((e) => { e.style.clipPath = cp; });
      }, 'inOutCubic');
      o.layers.forEach((e) => A.tween(e, t, d * 0.6, { opacity: [1, 0] }, 'inQuad'));
    },
    'blur-dissolve'(o, i, t, d) {
      A.tween(i.plate, t, d, { opacity: [0, 1], blur: [14, 0], scale: [1.04, 1] }, 'outCubic');
      i.layers.forEach((e) => A.tween(e, t + d * 0.3, d * 0.7, { opacity: [0, 1] }, 'outCubic'));
      o.layers.forEach((e) => A.tween(e, t, d * 0.6, { opacity: [1, 0] }, 'inQuad'));
    },
    shutter(o, i, t, d) {
      A.fn(t, t + d, (u) => { const cp = u >= 1 ? 'none' : u <= 0 ? 'polygon(0 0,0 0,0 0)' : band(7, u, RTL); i.plate.style.clipPath = cp; i.layers.forEach((e) => { e.style.clipPath = cp; }); }, 'inOutCubic');
      o.layers.forEach((e) => A.tween(e, t, d * 0.5, { opacity: [1, 0] }, 'inQuad'));
    },
    'glitch-cut'(o, i, t, d) {
      const r = rng(Math.round(t * 1000));
      const jit = [];
      for (let k = 0; k < 9; k++) jit.push([r() - 0.5, r()]);
      A.fn(t, t + d, (u, tt) => {
        const cp = u >= 1 ? 'none' : u <= 0 ? 'polygon(0 0,0 0,0 0)' : band(9, Math.min(1, u * 1.6), jit[Math.floor(u * 8)][1] > 0.5);
        i.plate.style.clipPath = cp; i.layers.forEach((e) => { e.style.clipPath = cp; });
        const j = u >= 1 ? 0 : jit[Math.floor(u * 8)][0] * 70 * (1 - u);
        i.plate.style.translate = `${j}px 0`; o.plate.style.translate = `${-j}px 0`;
      }, 'linear');
      A.tween(i.plate, t, d, { brightness: [1.7, 1] }, 'outCubic');
      o.layers.forEach((e) => A.tween(e, t, d * 0.4, { opacity: [1, 0] }, 'inQuad'));
    },
  };

  // ------------------------------------------------------------------ scenes
  const SC = SB.scenes;
  const flash = el('div'); flash.id = 'flash'; flash.style.background = 'var(--paper)'; G.fx.appendChild(flash);
  flash.__base = { opacity: 0 }; A.show(flash, -1, 1e6);
  const sceneObjs = SC.map((S, idx) => {
    const pw = el('div', 'wrap'), bw = el('div', 'wrap'), fw = el('div', 'wrap');
    G.plates.appendChild(pw); G.back.appendChild(bw); G.front.appendChild(fw);
    const o = { S, plate: pw, back: bw, front: fw, layers: [bw, fw], vFrom: S.start, vTo: S.end };
    // plate + camera
    const P = S.plate || {};
    if (P.src || P.bg || P.stage) {
      const cam = el('div', 'cam'); pw.appendChild(cam);
      if (P.bg) cam.style.background = col(P.bg);
      const punch = el('div', 'wrap'); cam.appendChild(punch);
      if (P.stage) {
        // 2.5D: flat image pieces placed in 3D space, real perspective camera moves through them (no video model)
        const ST = P.stage, Pp = ST.perspective || 1400, depthC = ST.center === undefined ? -300 : ST.center;
        const wrap3 = el('div', 'stage3d'); wrap3.style.perspective = Pp + 'px'; const po = ST.origin || [0.5, 0.42]; wrap3.style.perspectiveOrigin = `${po[0] * 100}% ${po[1] * 100}%`;
        const world = el('div', 'world3d'); wrap3.appendChild(world); punch.appendChild(wrap3);
        (ST.layers || []).forEach((L, li) => {
          const z = L.z || 0; const d = el('div', 'layer3d'); const im = el('img'); im.src = L.src; d.appendChild(im); decodes.push(im);
          const wpx = (L.w === undefined ? 1.15 : L.w) * W * (Pp - z) / Pp; d.style.width = px(wpx);
          if (L.blur) d.style.filter = `blur(${L.blur}px)`; if (L.brightness) d.style.filter = (d.style.filter || '') + ` brightness(${L.brightness})`;
          const ax = L.anchor === 'bottom' ? 100 : L.anchor === 'top' ? 0 : 50; d.style.transformOrigin = `50% ${ax}%`;
          const bx = (L.x || 0) * W, by = (L.y || 0) * H, ph = li * 1.7, fl = L.float || 0;
          d.__set = (t) => { const bob = fl ? Math.sin(t * 1.3 + ph) * fl : 0; d.style.transform = `translate3d(${bx}px, ${by + bob}px, ${z}px) translate(-50%, -${ax}%)`; };
          d.style.left = '50%'; d.style.top = (L.anchor === 'bottom' ? (L.top === undefined ? 100 : L.top * 100) : L.anchor === 'top' ? 0 : 50) + '%';
          world.appendChild(d); d.__set(0); world.__layers = (world.__layers || []).concat(d);
        });
        const C0 = ST.camera || {}; const mv = C0.move || 'dolly-in', amp = C0.amount === undefined ? 1 : C0.amount, tA = S.start, tB = S.end + (SC[idx + 1] && SC[idx + 1].transition ? SC[idx + 1].transition.dur : 0);
        const set = (u, t) => {
          const e = 0.5 - 0.5 * Math.cos(Math.PI * Math.min(1, Math.max(0, u)));
          let tx = 0, ty = 0, tz = 0, ry = 0, rx = 0;
          if (mv === 'dolly-in') tz = Pp * 0.30 * amp * e; else if (mv === 'dolly-out') tz = Pp * 0.30 * amp * (1 - e);
          else if (mv === 'truck-left') { tx = W * 0.07 * amp * (e - 0.5) * 2; tz = Pp * 0.06 * amp * e; } else if (mv === 'truck-right') { tx = -W * 0.07 * amp * (e - 0.5) * 2; tz = Pp * 0.06 * amp * e; }
          else if (mv === 'crane-up') { ty = H * 0.05 * amp * (e - 0.5) * 2; tz = Pp * 0.08 * amp * e; } else if (mv === 'crane-down') { ty = -H * 0.05 * amp * (e - 0.5) * 2; tz = Pp * 0.08 * amp * e; }
          else if (mv === 'orbit-left') { ry = -5 * amp * (e - 0.5) * 2; tz = Pp * 0.10 * amp * e; } else if (mv === 'orbit-right') { ry = 5 * amp * (e - 0.5) * 2; tz = Pp * 0.10 * amp * e; }
          else if (mv === 'drift') { tx = W * 0.025 * amp * Math.sin(u * 3.1); ty = H * 0.012 * amp * Math.cos(u * 2.3); tz = Pp * 0.12 * amp * e; ry = 1.6 * amp * Math.sin(u * 2.0); }
          world.style.transform = `translate3d(${tx}px, ${ty}px, ${tz}px) translateZ(${depthC}px) rotateY(${ry}deg) rotateX(${rx}deg) translateZ(${-depthC}px)`;
        };
        A.show(wrap3, tA - 0.05, tB + 0.05);
        A.fn(tA, tB, (u, t) => { set(u, t); (world.__layers || []).forEach((d) => d.__set(t)); }, 'linear');
        set(0, tA);
      } else if (P.src) {
        const im = el('img', 'plate-img'); im.src = P.src; punch.appendChild(im); decodes.push(im);
        const f = P.focus || [0.5, 0.5]; im.style.transformOrigin = `${f[0] * 100}% ${f[1] * 100}%`;
        const t0 = S.start, t1 = S.end + (SC[idx + 1] && SC[idx + 1].transition ? SC[idx + 1].transition.dur : 0), mv = P.move || 'push-in', amp = P.amount || 1;
        const ease = 'inOutSine';
        if (mv === 'push-in') A.tween(im, t0, t1 - t0, { scale: [1.04, 1.04 + 0.13 * amp] }, ease);
        else if (mv === 'pull-out') A.tween(im, t0, t1 - t0, { scale: [1.04 + 0.13 * amp, 1.04] }, ease);
        else if (mv === 'pan-left') A.tween(im, t0, t1 - t0, { scale: [1.14, 1.14], x: [W * 0.035 * amp, -W * 0.035 * amp] }, ease);
        else if (mv === 'pan-right') A.tween(im, t0, t1 - t0, { scale: [1.14, 1.14], x: [-W * 0.035 * amp, W * 0.035 * amp] }, ease);
        else if (mv === 'pan-up') A.tween(im, t0, t1 - t0, { scale: [1.14, 1.14], y: [H * 0.03 * amp, -H * 0.03 * amp] }, ease);
        else if (mv === 'pan-down') A.tween(im, t0, t1 - t0, { scale: [1.14, 1.14], y: [-H * 0.03 * amp, H * 0.03 * amp] }, ease);
        else if (mv === 'drift') { const rr = rng(idx * 31 + 7); const ax = (rr() - 0.5) * W * 0.04, ay = (rr() - 0.5) * H * 0.03; A.tween(im, t0, t1 - t0, { scale: [1.08, 1.12], x: [-ax, ax], y: [ay, -ay] }, ease); }
        else A.set(im, t0, { scale: [P.scale || 1, P.scale || 1] });
        (P.beats || []).forEach((b) => {
          if (b.kind === 'shake') { const rr = rng(Math.round(b.at * 100)); A.fn(b.at, b.at + 0.4, (u) => { const k = (1 - u) * (b.amt || 14); punch.style.translate = `${((rr() - 0.5) * k).toFixed(1)}px ${((rr() - 0.5) * k).toFixed(1)}px`; if (u >= 1) punch.style.translate = '0 0'; }); }
          else { A.tween(punch, b.at, 0.12, { scale: [1, 1 + (b.amt || 0.06)] }, 'outCubic'); A.tween(punch, b.at + 0.12, 0.35, { scale: [1 + (b.amt || 0.06), 1] }, 'outCubic'); }
        });
      }
      if (P.tint) { const tn = el('div', 'tint'); tn.style.background = P.tint; tn.style.opacity = P.tintOpacity === undefined ? 0.35 : P.tintOpacity; cam.appendChild(tn); }
      if (P.shade) { const sh = el('div', 'wrap'); sh.style.background = `linear-gradient(180deg, rgba(0,0,0,${P.shade}) 0%, rgba(0,0,0,0) 38%, rgba(0,0,0,0) 62%, rgba(0,0,0,${P.shade * 1.3}) 100%)`; cam.appendChild(sh); }
    }
    (S.layers || []).forEach((L) => {
      const fn = build[L.type];
      if (!fn) { console.warn('unknown layer', L.type); return; }
      fn(L, S, { back: bw, front: fw });
    });
    return o;
  });
  // overlaps + transitions
  sceneObjs.forEach((o, idx) => {
    const S = o.S; const X = { flash, inFrom: S.start, outTo: null };
    if (idx > 0 && S.transition && S.transition.type !== 'cut' && TR[S.transition.type]) {
      const prev = sceneObjs[idx - 1]; const d = S.transition.dur;
      X.outTo = null; prev.vTo = S.start + d;
      TR[S.transition.type]({ plate: prev.plate, layers: prev.layers }, { plate: o.plate, layers: o.layers }, S.start, d, S, X);
      if (X.outTo !== null) prev.vTo = X.outTo + 0.02;
      o.vFrom = X.inFrom;
    }
  });
  sceneObjs.forEach((o) => { [o.plate, o.back, o.front].forEach((e) => A.show(e, o.vFrom - 0.02, o.vTo + 0.02)); });

  // ------------------------------------------------------------------ avatar
  const AV = SB.avatar;
  let avImg = null, avWrap = null, avLoadedIdx = -1;
  if (AV && AV.frames) {
    const hFrac = AV.heightFrac || 0.4; let ah = H * hFrac, aw = ah * (AV.width / AV.height);
    const maxw = W * (AV.maxWidthFrac || 1.08); if (aw > maxw) { aw = maxw; ah = aw * (AV.height / AV.width); }
    avWrap = el('div', 'av' + (AV.opaque ? ' opaque' : '')); avWrap.style.width = px(aw); avWrap.style.height = px(ah); avWrap.style.marginLeft = px(-aw / 2);
    avWrap.style.bottom = px(-(AV.bleed === undefined ? 0.012 : AV.bleed) * H);
    avWrap.__base = { opacity: 0 }; if (!AV.opaque) avWrap.__filter = 'drop-shadow(0 -8px 38px rgba(0,0,0,0.38))';
    avImg = el('img'); avWrap.appendChild(avImg); G.avatar.appendChild(avWrap); avWrap.__dims = [aw, ah];
    (AV.windows || []).forEach((w) => {
      const en = w.enter || 'rise', ex = w.exit || 'fall', dx = (w.x || 0) * W;
      avWrap.__base.x = dx;
      const t0 = w.t0, t1 = w.t1;
      if (en === 'rise') { A.tween(avWrap, t0, 0.55, { yp: [104, 0], x: [dx, dx] }, 'outBackSoft'); }
      else if (en === 'pop') A.tween(avWrap, t0, 0.4, { scale: [0.82, 1], opacity: [0, 1], x: [dx, dx] }, 'outBack');
      else if (en === 'slide-left') A.tween(avWrap, t0, 0.5, { x: [dx - W, dx], opacity: [1, 1] }, 'outExpo');
      else if (en === 'slide-right') A.tween(avWrap, t0, 0.5, { x: [dx + W, dx], opacity: [1, 1] }, 'outExpo');
      else if (en === 'fade') A.tween(avWrap, t0, 0.35, { opacity: [0, 1], x: [dx, dx] }, 'outCubic');
      else A.set(avWrap, t0, { opacity: [0, 1], x: [dx, dx] });
      if (en === 'rise') A.set(avWrap, t0, { opacity: [0, 1] });
      if (t1 < SB.meta.duration - 0.05) {
        if (ex === 'fall') { A.tween(avWrap, t1 - 0.35, 0.35, { yp: [0, 104] }, 'inCubic'); A.set(avWrap, t1, { opacity: [1, 0] }); A.set(avWrap, t1 + 0.01, { yp: [104, 0] }); }
        else if (ex === 'fade') A.tween(avWrap, t1 - 0.3, 0.3, { opacity: [1, 0] }, 'inCubic');
        else if (ex === 'slide-left') { A.tween(avWrap, t1 - 0.4, 0.4, { x: [dx, dx - W] }, 'inExpo'); A.set(avWrap, t1, { opacity: [1, 0] }); A.set(avWrap, t1 + 0.01, { x: [dx - W, dx] }); }
        else if (ex === 'slide-right') { A.tween(avWrap, t1 - 0.4, 0.4, { x: [dx, dx + W] }, 'inExpo'); A.set(avWrap, t1, { opacity: [1, 0] }); A.set(avWrap, t1 + 0.01, { x: [dx + W, dx] }); }
        else A.set(avWrap, t1, { opacity: [1, 0] });
      }
    });
  }
  function avatarVisibleAt(t) { return (AV && AV.windows || []).some((w) => t >= w.t0 && t <= w.t1); }
  async function setAvatar(t) {
    if (!avImg || !avatarVisibleAt(t)) return;
    const idx = clamp(Math.floor((t - (AV.offset || 0)) * AV.fps) + 1, 1, AV.frames);
    if (idx === avLoadedIdx) return;
    avLoadedIdx = idx;
    const url = `${AV.dir}/a_${String(idx).padStart(5, '0')}.webp`;
    const im = new Image(); im.src = url;
    try { await im.decode(); } catch (e) { /* keep previous frame */ }
    avImg.src = url;
    try { await avImg.decode(); } catch (e) { /* ignore */ }
  }

  // --------------------------------------------------------------- captions
  function chunkWords() {
    const Cc = SB.captions || {}; const max = Cc.max || 3, maxChars = Cc.maxChars || 24; const ws = SB.words; const starts = SC.map((s) => s.start);
    const chunks = []; let cur = [];
    const flush = () => { if (cur.length) { chunks.push(cur); cur = []; } };
    ws.forEach((w, i) => {
      if (cur.length && starts.some((s) => Math.abs(s - w.start) < 0.06)) flush();
      cur.push(w);
      const nxt = ws[i + 1]; const chars = cur.reduce((a, x) => a + x.w.length + 1, 0);
      if (cur.length >= max || chars >= maxChars || /[,.;:!?…]$/.test(w.w) || (nxt && nxt.start - w.end > 0.28)) flush();
    });
    flush(); return chunks;
  }
  function capY(t) {
    const z = (SB.captions && SB.captions.zones) || []; let y = 0.8;
    for (const s of z) if (t >= s.t0 - 0.001) y = s.y;
    return y;
  }
  if (SB.captions && SB.captions.style !== 'none' && SB.words && SB.words.length) {
    const style = SB.captions.style || WD.captions || 'word-pop'; const size = SB.captions.size || 60;
    const keys = (SB.captions.key_words || []).map((s) => s.replace(/[^\w֐-׿]/g, ''));
    chunkWords().forEach((ch) => {
      const t0 = ch[0].start, t1 = Math.max(ch[ch.length - 1].end + 0.12, t0 + 0.35);
      const cap = el('div', `cap s-${style}`); const line = el('div', 'line'); line.style.fontSize = px(size); cap.appendChild(line);
      cap.style.top = px(capY(t0) * H - size * 0.6);
      const ws = ch.map((w) => {
        const s = el('span', 'cw', esc(w.w)); if (keys.includes(w.w.replace(/[^\w֐-׿]/g, ''))) s.classList.add('key'); line.appendChild(s); line.appendChild(document.createTextNode(' ')); return s;
      });
      addFit(line, { w: W - 150, h: size * 1.6, min: 30, max: size, wrap: false });
      ws.forEach((s, i) => {
        const w = ch[i];
        if (style === 'word-pop' || style === 'bounce') {
          A.tween(s, w.start, style === 'bounce' ? 0.38 : 0.2, style === 'bounce' ? { yp: [-60, 0], opacity: [0, 1] } : { scale: [1.35, 1], opacity: [0, 1] }, style === 'bounce' ? 'outBounce' : 'outBack');
        } else if (style === 'typewriter') { A.set(s, w.start, { opacity: [0, 1] }); }
        else if (style === 'karaoke-fill') {
          s.__base = { opacity: 1 }; s.style.opacity = 1; s.style.color = 'rgba(255,255,255,0.55)'; const fill = el('span', 'fill', esc(w.w)); s.appendChild(fill);
          A.fn(w.start, Math.max(w.end, w.start + 0.12), (u) => { const v = (1 - u) * 100; fill.style.clipPath = RTL ? `inset(0 0 0 ${v}%)` : `inset(0 ${v}% 0 0)`; });
        } else if (style === 'underline-sweep') {
          A.fn(w.start, Math.max(w.end, w.start + 0.12), (u) => { s.style.setProperty('--u', u); });
        } else if (style === 'box-highlight') {
          A.fn(w.start, w.start + 0.001, (u) => { s.style.background = u > 0 ? 'var(--accent)' : 'transparent'; });
          A.fn(w.end, w.end + 0.001, (u) => { if (u > 0) s.style.background = 'transparent'; });
        }
      });
      const hold = A.tween(cap, t0 - 0.04, 0.1, { opacity: [0, 1] }, 'outCubic'); A.tween(cap, t1 - 0.08, 0.08, { opacity: [1, 0] }, 'inQuad');
      G.caps.appendChild(cap); A.show(cap, t0 - 0.06, t1 + 0.02);
    });
  }

  // -------------------------------------------------------------------- fx
  const gr = el('div'); gr.id = 'grain'; const cv = document.createElement('canvas'); cv.width = cv.height = 256;
  { const g = cv.getContext('2d'), d = g.createImageData(256, 256), r = rng(5); for (let i = 0; i < d.data.length; i += 4) { const v = 90 + r() * 120; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; } g.putImageData(d, 0, 0); gr.style.backgroundImage = `url(${cv.toDataURL()})`; }
  gr.style.opacity = Math.min(0.6, (WD.grain || 0.1) * 2.2); G.fx.appendChild(gr);
  const vg = el('div'); vg.id = 'vignette'; vg.style.background = `radial-gradient(ellipse at 50% 46%, rgba(0,0,0,0) 52%, rgba(0,0,0,${(WD.vignette || 0.3).toFixed(2)}) 100%)`; G.fx.appendChild(vg);
  const gd = el('div'); gd.id = 'grade'; gd.style.background = WD.palette.bg; gd.style.opacity = 0.14; G.fx.appendChild(gd);
  G.fx.appendChild(flash);

  // ------------------------------------------------------------ cover mode
  function buildCover() {
    const C = SB.cover || {}; const v = Q.get('variant') || C.variant || 'hero';
    const root = el('div', 'wrap'); G.plates.appendChild(root);
    const plate = C.plate || (SC[0].plate && SC[0].plate.src);
    if (plate) { const im = el('img', 'plate-img'); im.src = plate; root.appendChild(im); decodes.push(im); im.style.transform = 'scale(1.06)'; }
    const sh = el('div', 'wrap'); sh.style.background = 'linear-gradient(180deg, rgba(0,0,0,.35), rgba(0,0,0,0) 40%, rgba(0,0,0,.45))'; root.appendChild(sh);
    if (v === 'type') { root.style.background = 'var(--bg)'; if (root.firstChild && root.firstChild.tagName === 'IMG') root.firstChild.style.opacity = 0.35; sh.style.background = 'linear-gradient(180deg, rgba(0,0,0,.1), rgba(0,0,0,.55))'; }
    // presenter
    if (AV && AV.frames && v !== 'type') {
      const frame = clamp(Math.floor((C.avatar_time || 0.6) * AV.fps) + 1, 1, AV.frames);
      const fr = v === 'portrait' ? 0.62 : 0.44; let ah = H * fr, aw = ah * (AV.width / AV.height); if (aw > W * 1.1) { aw = W * 1.1; ah = aw * (AV.height / AV.width); }
      const a = el('div', 'av' + (AV.opaque ? ' opaque' : '')); a.style.width = px(aw); a.style.height = px(ah); a.style.marginLeft = px(-aw / 2); a.style.bottom = px(-0.012 * H);
      if (!AV.opaque) a.style.filter = 'drop-shadow(0 -8px 38px rgba(0,0,0,0.38))';
      const im = el('img'); im.src = `${AV.dir}/a_${String(frame).padStart(5, '0')}.webp`; a.appendChild(im); G.avatar.appendChild(a); decodes.push(im);
    }
    const head = C.headline || (SB.meta.title || '');
    const L = { text: head, style: C.style || (v === 'type' ? 'plain' : 'plain'), pos: v === 'portrait' ? [0.5, 0.2] : v === 'type' ? [0.5, 0.45] : [0.5, 0.22], size: v === 'type' ? 230 : 190, w: 0.92, maxh: v === 'type' ? 0.6 : 0.34, anim: 'none', at: -5, until: 1e6, settle: false };
    const wrap = mkPos(L, 'upper', 0.92); const inner = el('div', 'in'); const box = el('div', `hl hl-${L.style}`); box.style.fontSize = px(L.size); words(box, head); inner.appendChild(box); wrap.appendChild(inner); G.front.appendChild(wrap);
    addFit(box, { w: 0.92 * W, h: L.maxh * H, min: 50, max: L.size });
    if (C.sub) { const sw = mkPos({ pos: [0.5, v === 'type' ? 0.7 : 0.38], w: 0.8 }, 'mid', 0.8); const sb = el('div', 'hl hl-label', esc(C.sub)); sb.style.fontSize = px(64); sw.appendChild(sb); G.front.appendChild(sw); }
  }
  if (MODE === 'cover') buildCover();

  // ------------------------------------------------------------------- api
  A.finalize();
  function runFits() {
    fits.forEach((f) => {
      const e = f.el; let lo = f.min, hi = f.max, best = f.min;
      const hide = []; let p = e; while (p && p !== stage) { if (getComputedStyle(p).display === 'none') { hide.push([p, p.style.display]); p.style.display = 'block'; p.style.visibility = 'hidden'; } p = p.parentElement; }
      for (let i = 0; i < 12; i++) {
        const mid = (lo + hi) / 2; e.style.fontSize = mid + 'px';
        const r = e.getBoundingClientRect(); const wide = f.wrap === false ? e.scrollWidth > f.w : Math.max(e.scrollWidth, r.width) > f.w + 1;
        const ok = !wide && r.height <= f.h; if (ok) { best = mid; lo = mid; } else hi = mid;
      }
      e.style.fontSize = best + 'px';
      hide.forEach(([n, d]) => { n.style.display = d; n.style.visibility = ''; });
    });
  }
  const grainRng = (n) => ((n * 2654435761) >>> 0) % 256;
  window.__ready = (async () => {
    try { await document.fonts.ready; await Promise.all([...new Set(['Heebo', WD.type.display, WD.type.body])].map((f) => document.fonts.load(`${WD.type.weight} 80px "${f}"`, 'אבגabc').catch(() => {}))); } catch (e) {}
    await Promise.all(decodes.map((im) => (im.decode ? im.decode().catch(() => {}) : null)));
    runFits(); preps.forEach((f) => f());
    // first avatar frame
    if (MODE !== 'cover') { await setAvatar(0.0); }
    return true;
  })();
  window.__seek = async (t) => {
    await window.__ready;
    A.seek(t);
    const f = Math.round(t * FPS);
    gr.style.backgroundPosition = `${grainRng(f * 7)}px ${grainRng(f * 13 + 5)}px`;
    await setAvatar(t);
    return true;
  };
  // QA: rectangles of every layer on screen at time t
  window.__qa = async (t) => {
    await window.__seek(t);
    const rects = [];
    [G.back, G.front].forEach((g) => g.querySelectorAll('.pos, .card, .sticker, .hl, .counter, .lower, .quote').forEach((e) => {
      const cs = getComputedStyle(e); const r = e.getBoundingClientRect();
      let vis = cs.display !== 'none' && r.width > 4 && r.height > 4; let p = e; let op = 1; while (p && p !== stage) { const c2 = getComputedStyle(p); if (c2.display === 'none') vis = false; op *= parseFloat(c2.opacity); p = p.parentElement; }
      if (vis && op > 0.35 && e.classList.contains('hl')) rects.push({ kind: 'headline', text: e.textContent.trim().slice(0, 40), x: r.x, y: r.y, w: r.width, h: r.height, sw: e.scrollWidth, cw: e.clientWidth });
      else if (vis && op > 0.35 && (e.classList.contains('card') || e.classList.contains('sticker') || e.classList.contains('counter'))) rects.push({ kind: e.className.split(' ')[0], text: e.textContent.trim().slice(0, 30), x: r.x, y: r.y, w: r.width, h: r.height });
    }));
    const caps = []; G.caps.querySelectorAll('.cap').forEach((e) => { if (getComputedStyle(e).display !== 'none' && parseFloat(getComputedStyle(e).opacity) > 0.3) { const r = e.querySelector('.line').getBoundingClientRect(); caps.push({ x: r.x, y: r.y, w: r.width, h: r.height, text: e.textContent.trim() }); } });
    let face = null;
    if (avWrap && avatarVisibleAt(t) && parseFloat(getComputedStyle(avWrap).opacity) > 0.5) { const r = avWrap.getBoundingClientRect(); const f = AV.face || [0.22, 0.02, 0.78, 0.4]; face = { x: r.x + f[0] * r.width, y: r.y + f[1] * r.height, w: (f[2] - f[0]) * r.width, h: (f[3] - f[1]) * r.height }; }
    return { t, rects, caps, face, W, H };
  };
  window.__info = { W, H, FPS, duration: SB.meta.duration, mode: MODE };
})();

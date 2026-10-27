/* Deterministic animation engine.
 *
 * Every property is a pure function of time: seek(t) can be called in any order, from any worker, and always gives the
 * same pixels. There is no play head, no requestAnimationFrame, no library state.
 */
(function () {
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const lerp = (a, b, u) => a + (b - a) * u;

  const EASE = {
    linear: (t) => t,
    inQuad: (t) => t * t,
    outQuad: (t) => 1 - (1 - t) * (1 - t),
    inOutQuad: (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2),
    inCubic: (t) => t * t * t,
    outCubic: (t) => 1 - Math.pow(1 - t, 3),
    inOutCubic: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
    outQuart: (t) => 1 - Math.pow(1 - t, 4),
    inOutQuart: (t) => (t < 0.5 ? 8 * t * t * t * t : 1 - Math.pow(-2 * t + 2, 4) / 2),
    outExpo: (t) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t)),
    inExpo: (t) => (t <= 0 ? 0 : Math.pow(2, 10 * t - 10)),
    inOutExpo: (t) => (t <= 0 ? 0 : t >= 1 ? 1 : t < 0.5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2),
    inOutSine: (t) => -(Math.cos(Math.PI * t) - 1) / 2,
    outSine: (t) => Math.sin((t * Math.PI) / 2),
    outBack: (t) => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
    outBackSoft: (t) => { const c1 = 0.9, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
    outBackHard: (t) => { const c1 = 2.6, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
    outElastic: (t) => (t <= 0 ? 0 : t >= 1 ? 1 : Math.pow(2, -9 * t) * Math.sin(((t * 10 - 0.75) * (2 * Math.PI)) / 3) + 1),
    outBounce: (t) => {
      const n1 = 7.5625, d1 = 2.75;
      if (t < 1 / d1) return n1 * t * t;
      if (t < 2 / d1) return n1 * (t -= 1.5 / d1) * t + 0.75;
      if (t < 2.5 / d1) return n1 * (t -= 2.25 / d1) * t + 0.9375;
      return n1 * (t -= 2.625 / d1) * t + 0.984375;
    },
  };

  const BASE = { x: 0, y: 0, xp: 0, yp: 0, scale: 1, scaleX: 1, scaleY: 1, rotate: 0, rotateX: 0, rotateY: 0, skewX: 0, skewY: 0,
    opacity: 1, blur: 0, brightness: 1, saturate: 1, contrast: 1, hue: 0 };

  function interp(a, b, u) {
    if (Array.isArray(a)) return a.map((v, i) => lerp(v, b[i], u));
    return lerp(a, b, u);
  }

  class Anim {
    constructor() { this.recs = new Map(); this.fns = []; this.vis = []; this.maxT = 0; }

    rec(el) {
      let r = this.recs.get(el);
      if (!r) { r = { el, props: {}, base: Object.assign({}, BASE, el.__base || {}) }; this.recs.set(el, r); }
      return r;
    }

    /** spec: {prop:[from,to]} (explicit) or {prop:to} (from = where the last tween ended, or the base value). */
    tween(el, t0, dur, spec, ease = 'outCubic') {
      const r = this.rec(el);
      const fn = typeof ease === 'function' ? ease : EASE[ease] || EASE.outCubic;
      for (const [p, v] of Object.entries(spec)) {
        const arr = r.props[p] || (r.props[p] = []);
        let from, to;
        if (Array.isArray(v) && v.length === 2 && (Array.isArray(v[0]) || typeof v[0] === 'number' || Array.isArray(v[1]))) { from = v[0]; to = v[1]; }
        else { to = v; from = arr.length ? arr[arr.length - 1].to : (r.base[p] !== undefined ? r.base[p] : 0); }
        arr.push({ t0, t1: t0 + Math.max(dur, 1e-4), from, to, ease: fn });
        this.maxT = Math.max(this.maxT, t0 + dur);
      }
      return this;
    }

    /** Step to a value at time t (instant). */
    set(el, t, spec) { return this.tween(el, t, 1e-4, spec, 'linear'); }

    /** fn(u) is called on every seek with u in [0,1] (0 before t0, 1 after t1). */
    fn(t0, t1, cb, ease = 'linear') { this.fns.push({ t0, t1: Math.max(t1, t0 + 1e-4), cb, ease: EASE[ease] || EASE.linear }); return this; }

    /** display on/off window. */
    show(el, t0, t1, display = 'block') { this.vis.push({ el, t0, t1, display }); return this; }

    finalize() {
      for (const r of this.recs.values()) for (const p of Object.keys(r.props)) r.props[p].sort((a, b) => a.t0 - b.t0);
    }

    static value(arr, t) {
      if (t < arr[0].t0) return arr[0].from;
      let seg = arr[0];
      for (let i = 0; i < arr.length; i++) { if (arr[i].t0 <= t) seg = arr[i]; else break; }
      if (t >= seg.t1) return seg.to;
      return interp(seg.from, seg.to, seg.ease((t - seg.t0) / (seg.t1 - seg.t0)));
    }

    seek(t) {
      for (const v of this.vis) {
        const on = t >= v.t0 && t <= v.t1;
        const d = on ? v.display : 'none';
        if (v.el.style.display !== d) v.el.style.display = d;
      }
      for (const r of this.recs.values()) {
        const s = Object.assign({}, r.base);
        for (const p of Object.keys(r.props)) s[p] = Anim.value(r.props[p], t);
        apply(r.el, s);
      }
      for (const f of this.fns) f.cb(f.ease(clamp((t - f.t0) / (f.t1 - f.t0))), t);
    }
  }

  function apply(el, s) {
    const parts = [];
    if (s.x || s.y || s.xp || s.yp) parts.push(`translate(calc(${s.xp}% + ${s.x}px), calc(${s.yp}% + ${s.y}px))`);
    if (s.rotateX || s.rotateY) parts.push(`perspective(1200px) rotateX(${s.rotateX}deg) rotateY(${s.rotateY}deg)`);
    if (s.rotate) parts.push(`rotate(${s.rotate}deg)`);
    if (s.skewX || s.skewY) parts.push(`skew(${s.skewX}deg, ${s.skewY}deg)`);
    if (s.scale !== 1 || s.scaleX !== 1 || s.scaleY !== 1) parts.push(`scale(${s.scale * s.scaleX}, ${s.scale * s.scaleY})`);
    const tf = parts.length ? parts.join(' ') : 'none';
    if (el.__tf !== tf) { el.style.transform = tf; el.__tf = tf; }
    const op = String(+s.opacity.toFixed(4));
    if (el.__op !== op) { el.style.opacity = op; el.__op = op; }
    const fl = [];
    if (s.blur > 0.05) fl.push(`blur(${s.blur.toFixed(2)}px)`);
    if (s.brightness !== 1) fl.push(`brightness(${s.brightness.toFixed(3)})`);
    if (s.saturate !== 1) fl.push(`saturate(${s.saturate.toFixed(3)})`);
    if (s.contrast !== 1) fl.push(`contrast(${s.contrast.toFixed(3)})`);
    if (s.hue) fl.push(`hue-rotate(${s.hue}deg)`);
    const base = el.__filter || '';
    const f = (base + ' ' + fl.join(' ')).trim() || 'none';
    if (el.__fl !== f) { el.style.filter = f; el.__fl = f; }
    if (s.clip !== undefined) {
      const c = Array.isArray(s.clip) ? `inset(${s.clip.map((v) => v.toFixed(2) + '%').join(' ')})` : 'none';
      if (el.__cl !== c) { el.style.clipPath = c; el.__cl = c; }
    }
    if (s.iris !== undefined) {
      const [r, cx, cy] = s.iris;
      const c = r >= 149 ? 'none' : `circle(${r.toFixed(2)}% at ${cx}% ${cy}%)`;
      if (el.__ir !== c) { el.style.clipPath = c; el.__ir = c; }
    }
    if (s.poly !== undefined) {
      const c = `polygon(${s.poly.map((v, i) => v.toFixed(2) + '%' + (i % 2 ? ',' : '')).join(' ')})`;
      if (el.__po !== c) { el.style.clipPath = c; el.__po = c; }
    }
    if (s.dash !== undefined && el.__len) {
      el.style.strokeDasharray = el.__len;
      el.style.strokeDashoffset = (el.__len * (1 - s.dash)).toFixed(2);
    }
  }

  // Seeded random so particles, jitter and grain are identical in every worker.
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  window.AVS = Object.assign(window.AVS || {}, { clamp, lerp, EASE, Anim, rng, BASE });
})();

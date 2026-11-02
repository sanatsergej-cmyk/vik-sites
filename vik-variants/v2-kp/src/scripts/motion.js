// Эффекты варианта V2: меню, появления, параллакс, ленты этапов и сквозной трубопровод на главной.
// Без JS и при prefers-reduced-motion весь контент виден сразу, линия нарисована целиком.

const root = document.documentElement;
const reduced = root.classList.contains('rm');
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));

/* ---------- меню ---------- */
const toggle = document.querySelector('[data-menu-toggle]');
const navEl = document.getElementById('main-nav');
if (toggle && navEl) {
  const set = (open) => {
    navEl.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', String(open));
    document.body.classList.toggle('menu-open', open);
  };
  toggle.addEventListener('click', () => set(!navEl.classList.contains('open')));
  navEl.addEventListener('click', (e) => { if (e.target.closest('a')) set(false); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') set(false); });
}

/* ---------- подвал: на телефоне колонки свёрнуты (аккордеон), без JS открыты ---------- */
if (window.matchMedia('(max-width: 767px)').matches) document.querySelectorAll('.fcol[open]').forEach((d) => d.removeAttribute('open'));

/* ---------- предзаполнение формы из адреса (?direction=&service=&stage=) ---------- */
const intake = document.querySelector('[data-intake]');
if (intake) {
  const p = new URLSearchParams(location.search);
  ['direction', 'service', 'stage'].forEach((k) => {
    const v = p.get(k);
    const el = intake.elements[k];
    if (v && el) el.value = v;
  });
}

/* ---------- появления ---------- */
const rv = [...document.querySelectorAll('.rv')];
if (!reduced && 'IntersectionObserver' in window) {
  root.classList.add('rv-on');
  const io = new IntersectionObserver((entries) => {
    entries.forEach((en) => { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  rv.forEach((el) => io.observe(el));
} else {
  rv.forEach((el) => el.classList.add('in'));
}

/* ---------- сквозной трубопровод (главная) ---------- */
const pipeRoot = document.querySelector('[data-pipe-root]');
const pipeStart = document.querySelector('[data-pipe-start]');
const NS = 'http://www.w3.org/2000/svg';
let pipe = null;

function mk(tag, attrs, parent) {
  const n = document.createElementNS(NS, tag);
  Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
  if (parent) parent.appendChild(n);
  return n;
}

function buildPipe() {
  if (!pipeRoot || !pipeStart) return;
  const end = document.getElementById('intake');
  if (!end) return;
  if (pipe) pipe.layer.remove();
  const rr = pipeRoot.getBoundingClientRect();
  const W = pipeRoot.clientWidth, H = pipeRoot.scrollHeight;
  const ox = rr.left, oy = rr.top;
  const pos = (el) => { const b = el.getBoundingClientRect(); return { x: b.left - ox + b.width / 2, y: b.top - oy + b.height / 2, top: b.top - oy }; };
  const s = pos(pipeStart);
  const hero = document.querySelector('[data-hero]');
  const heroB = hero ? hero.getBoundingClientRect().bottom - oy : s.y + 120;
  const anchors = [...pipeRoot.querySelectorAll('[data-pipe-node]')].map((el) => ({ el, ...pos(el) })).filter((a) => a.y > heroB);
  const mobile = W < 900;
  const first = anchors[0];
  const L = mobile ? 8 : Math.max(12, (first ? first.x : 60) - 34);
  const endY = end.getBoundingClientRect().top - oy + (mobile ? 64 : 96);
  const r = mobile ? 14 : 26;
  const yTurn = heroB - (mobile ? 28 : 56);
  const sx = s.x, sy = s.y + pipeStart.offsetHeight / 2;
  const y1 = Math.max(sy + 8, yTurn - r);

  // M старт → вниз → дуга влево → горизонталь → дуга вниз → магистраль до формы
  const d = `M${sx} ${sy} V${y1} A${r} ${r} 0 0 1 ${sx - r} ${y1 + r} H${L + r} A${r} ${r} 0 0 0 ${L} ${y1 + 2 * r} V${endY}`;
  const seg1 = y1 - sy;
  const arc = (Math.PI * r) / 2;
  const horiz = Math.max(0, sx - r - (L + r));
  const runStart = seg1 + arc + horiz + arc; // длина до начала магистрали
  const trunkY0 = y1 + 2 * r;
  const total = runStart + (endY - trunkY0);

  const layer = document.createElement('div');
  layer.className = 'pipe-layer';
  layer.setAttribute('aria-hidden', 'true');
  const svg = mk('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` }, layer);
  mk('path', { d, class: 'pipe-track' }, svg);
  mk('path', { d, class: 'pipe-body' }, svg);
  const line = mk('path', { d, class: 'pipe-line' }, svg);
  line.style.strokeDasharray = `${total} ${total}`;
  const body = svg.children[1];
  body.style.strokeDasharray = `${total} ${total}`;

  const nodes = anchors.map((a) => {
    const g = mk('g', { class: 'pipe-node' }, svg);
    const nx = mobile ? L : a.x;
    if (!mobile && a.x - L > 6) {
      const stub = mk('path', { d: `M${L} ${a.y} H${a.x - 7}`, class: 'pipe-stub' }, g);
      stub.style.strokeDasharray = `${a.x - 7 - L} ${a.x - 7 - L}`;
      stub.style.strokeDashoffset = `${a.x - 7 - L}`;
      mk('path', { d: `M${L + 10} ${a.y - 5} v10`, class: 'pipe-flange' }, g);
    }
    mk('circle', { cx: nx, cy: a.y, r: mobile ? 5 : 7, class: 'pipe-ring' }, g);
    mk('circle', { cx: nx, cy: a.y, r: mobile ? 2 : 2.6, class: 'pipe-dot' }, g);
    return { g, el: a.el, len: runStart + Math.max(0, a.y - trunkY0) };
  });
  const head = mk('circle', { r: mobile ? 3.5 : 4.5, class: 'pipe-head' }, svg);
  const term = mk('g', { class: 'pipe-node pipe-term' }, svg);
  mk('circle', { cx: L, cy: endY, r: mobile ? 7 : 10, class: 'pipe-ring' }, term);
  mk('circle', { cx: L, cy: endY, r: mobile ? 3 : 4, class: 'pipe-dot' }, term);
  nodes.push({ g: term, el: end, len: total - 1 });

  pipeRoot.prepend(layer);
  pipe = { layer, line, body, head, nodes, total, sx, sy, seg1, runStart, trunkY0, y1, oyDoc: oy + window.scrollY, last: -1 };
  updatePipe(true);
}

function pointAt(D) {
  return pipe.line.getPointAtLength(clamp(D, 0, pipe.total));
}

function updatePipe(force) {
  if (!pipe) return;
  const vh = window.innerHeight;
  let D;
  if (reduced) D = pipe.total;
  else {
    const headY = window.scrollY + vh * 0.82 - pipe.oyDoc; // «голова» линии в координатах слоя
    const span = vh * 0.32; // за сколько прокрутки проходит горизонтальный участок
    if (headY <= pipe.sy) D = 0;
    else if (headY <= pipe.y1) D = headY - pipe.sy;
    else if (headY <= pipe.y1 + span) D = pipe.seg1 + ((headY - pipe.y1) / span) * (pipe.runStart - pipe.seg1);
    else D = pipe.runStart + (headY - span - pipe.y1);
    D = clamp(D, 0, pipe.total);
  }
  if (!force && Math.abs(D - pipe.last) < 0.5) return;
  pipe.last = D;
  const off = pipe.total - D;
  pipe.line.style.strokeDashoffset = off;
  pipe.body.style.strokeDashoffset = off;
  const p = pointAt(D);
  pipe.head.setAttribute('cx', p.x);
  pipe.head.setAttribute('cy', p.y);
  pipe.head.style.opacity = D > 2 && D < pipe.total - 2 ? '1' : '0';
  pipe.nodes.forEach((n) => {
    const on = D >= n.len;
    if (n.on !== on) {
      n.on = on;
      n.g.classList.toggle('on', on);
      const sec = n.el.closest('section');
      if (sec) sec.classList.toggle('is-connected', on);
    }
  });
}

/* ---------- ленты этапов ---------- */
const routes = [...document.querySelectorAll('[data-route]')].map((el) => ({ el, fill: el.querySelector('.route-fill'), steps: [...el.querySelectorAll('.route-step')] }));
function updateRoutes() {
  const vh = window.innerHeight;
  routes.forEach((r) => {
    const b = r.el.getBoundingClientRect();
    const p = reduced ? 1 : clamp((vh * 0.78 - b.top) / (b.height * 0.9 + vh * 0.2));
    r.el.style.setProperty('--p', p.toFixed(4));
    const n = r.steps.length;
    r.steps.forEach((s, i) => s.classList.toggle('on', p >= (n > 1 ? i / (n - 1) : 0) * 0.94 + 0.02));
  });
}

/* ---------- параллакс ---------- */
const par = [...document.querySelectorAll('[data-parallax]')].map((el) => ({ el, k: parseFloat(el.dataset.parallax) || 0.1 }));
function updateParallax() {
  if (reduced) return;
  const vh = window.innerHeight;
  par.forEach(({ el, k }) => {
    const b = el.parentElement.getBoundingClientRect();
    if (b.bottom < -100 || b.top > vh + 100) return;
    const c = b.top + b.height / 2 - vh / 2;
    // сдвиг не больше запаса от scale(1.14), иначе у кадра открывается край (тёмная полоса сверху/снизу)
    const room = (el.offsetHeight || b.height) * 0.065;
    const y = clamp(-c * k, -room, room);
    el.style.transform = `translate3d(0, ${y.toFixed(1)}px, 0) scale(1.14)`;
  });
}

/* ---------- шапка ---------- */
const header = document.querySelector('[data-header]');
function updateHeader() { if (header) header.classList.toggle('scrolled', window.scrollY > 8); }

/* ---------- статья: прогресс чтения и активный пункт оглавления ---------- */
const readBar = document.querySelector('[data-read-bar]');
const readBody = document.querySelector('[data-read-body]');
const tocLinks = [...document.querySelectorAll('[data-toc-link]')];
const tocTargets = tocLinks.map((a) => document.querySelector(a.getAttribute('href'))).filter(Boolean);
function updateReading() {
  if (!readBar || !readBody) return;
  const b = readBody.getBoundingClientRect();
  const vh = window.innerHeight;
  readBar.parentElement.style.setProperty('--rp', clamp((vh * 0.3 - b.top) / Math.max(1, b.height - vh * 0.5)).toFixed(4));
  let cur = -1;
  tocTargets.forEach((t, i) => { if (t.getBoundingClientRect().top < vh * 0.35) cur = i; });
  tocLinks.forEach((a, i) => a.classList.toggle('is-active', i === cur));
}

let ticking = false;
function frame() { ticking = false; updatePipe(false); updateRoutes(); updateParallax(); updateHeader(); updateReading(); }
function onScroll() { if (!ticking) { ticking = true; requestAnimationFrame(frame); } }

window.addEventListener('scroll', onScroll, { passive: true });
let rt;
window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { buildPipe(); frame(); }, 150); });
window.addEventListener('load', () => { buildPipe(); frame(); });
if ('ResizeObserver' in window && pipeRoot) {
  let lastH = 0;
  new ResizeObserver(() => {
    const h = pipeRoot.scrollHeight;
    if (Math.abs(h - lastH) > 40) { lastH = h; clearTimeout(rt); rt = setTimeout(() => { buildPipe(); frame(); }, 200); }
  }).observe(pipeRoot);
}
buildPipe();
frame();

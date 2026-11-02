// Автопроверка текстов сайта. Запуск: node scripts/check-content.mjs
import * as c from '../src/content/index.mjs';

const errors = [];
const warns = [];
const err = (m) => errors.push(m);
const warn = (m) => warns.push(m);

const pages = [
  { path: '/', ...c.home },
  ...c.directions.map((d) => ({ path: `/napravleniya/${d.slug}/`, ...d })),
  ...c.services.map((s) => ({ path: `/uslugi/${s.slug}/`, ...s })),
  { path: '/o-kompanii/', ...c.about },
  { path: '/proekty/', ...c.projects },
  { path: '/dokumenty/', ...c.documents },
  { path: '/kontakty/', ...c.contacts },
  { path: '/privacy/', ...c.privacy },
  { path: '/consent/', ...c.consent },
  { path: '/baza-znaniy/', ...c.knowledgeBase },
  ...c.articles.map((a) => ({ path: `/baza-znaniy/${a.slug}/`, ...a })),
];
const legal = new Set(['/privacy/', '/consent/']);
const known = new Set(pages.map((p) => p.path));

// 1. мета
const seen = { title: new Map(), description: new Map(), h1: new Map() };
for (const p of pages) {
  for (const k of ['title', 'description', 'h1']) {
    if (!p[k]) { err(`${p.path}: нет ${k}`); continue; }
    if (seen[k].has(p[k])) err(`${p.path}: ${k} дублирует ${seen[k].get(p[k])}`);
    seen[k].set(p[k], p.path);
  }
  if (p.title && p.title.length > 62) err(`${p.path}: title ${p.title.length} знаков (>62)`);
  if (p.description && (p.description.length > 165 || (p.description.length < 70 && !['/proekty/','/dokumenty/','/privacy/','/consent/'].includes(p.path)))) warn(`${p.path}: description ${p.description.length} знаков`);
}

// 2. тексты: собираем все строки
function strings(x, out = []) {
  if (typeof x === 'string') out.push(x);
  else if (Array.isArray(x)) x.forEach((i) => strings(i, out));
  else if (x && typeof x === 'object') Object.entries(x).forEach(([k, v]) => { if (k !== 'todo') strings(v, out); });
  return out;
}
const bundle = [
  ['common', [c.brand, c.principles, c.cta, c.stages, c.route, c.riskPoints, c.form, c.faqCommon, c.manufacturers, c.energy, c.companyBlock, c.cookie, c.footer]],
  ...pages.map((p) => [p.path, p]),
];

const L = '\\p{L}';
const forbidden = [
  [/гаранти/iu, 'гарантии без документов'], [/скидк/iu, 'скидки'], [/(?<!\p{L})акци[яи]/iu, 'акции'], [/срочно/iu, 'срочность'],
  [/лучш/iu, 'превосходная степень'], [/№ ?1(?!\d)/iu, '«№1»'], [/быстрее всех/iu, 'сравнение с конкурентами'],
  [/под ключ/iu, '«под ключ» (проверить границы)'], [/любой сложности/iu, '«любой сложности»'],
  [/потенциал/iu, '«Потенциал» исключён'], [/собственн\p{L}+ (парк|техник)/iu, 'собственный парк техники'],
  [/\d+\s*лет(?!\p{L})/iu, 'стаж без подтверждения'], [/(мы|являемся|как)\s+генеральн\p{L}+\s+подрядчик/iu, 'статус генподрядчика'], [/лицензи/iu, 'лицензии'],
  [/партнёр\p{L}* (МОЭК|Мосводоканал|Мосгаз)/iu, 'ложное партнёрство с РСО'], [/дилер/iu, 'дилерство'],
  [/лидер/iu, 'самоназвание лидером'], [/единственн/iu, '«единственный»'], [/уникальн/iu, '«уникальный»'], [/самы[йе] \p{L}+/iu, 'превосходная степень «самый …»'],
  [/наш\p{L}* объект/iu, '«наш объект» запрещён (ТЗ, раздел 1)'], [/(?<!\d)(44|223)-?ФЗ/iu, '44/223-ФЗ не упоминаем'],
  [/(?<!\p{L})(ГРПШ?|ГПА)(?!\p{L})/u, 'газ: ГРП/ГРПШ/ГПА не подтверждены'],
];
// газ: давления не называем до подтверждения состава работ
const gasOnly = [[/давлени|МПа|кПа/iu, 'газ: давления не подтверждены']];
// нормативные реквизиты (СП, ГОСТ, ПП, №, даты, пункты) не считаем цифрами о компании
// («от 2 часов» и прочие сроки/количества по-прежнему попадают в предупреждения)
const normRef = /(?<!\p{L})(СП|ГОСТ( Р)?|СНиП|РД|ПП РФ|ПУЭ|№|ст\.|п\.|ч\.)\s*[\d.\-\/*]+(\/пр|-ФЗ|-ПП|-ст)?|\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}/gu;
const digits = new Map();
for (const [where, data] of bundle) {
  const isLegal = legal.has(where);
  for (const s0 of strings(data)) {
    const s = s0.replace(/\u00a0/g, ' ');
    const scan = s.replace(/не (можем |могли бы )?гарантир[а-яё]*/giu, '').replace(/Статуса дилера или партнёра это не означает\./g, '');
    for (const [re, why] of forbidden) if (re.test(scan)) err(`${where}: «${s.slice(0, 70)}…» — ${why}`);
    if (where === '/napravleniya/gazosnabzhenie/') for (const [re, why] of gasOnly) if (re.test(scan)) err(`${where}: «${s.slice(0, 70)}…» — ${why}`);
    for (const w of s.split(/[\s—–,.;:!?()«»]+/)) {
      if (/[A-Za-z]/.test(w) && /[А-Яа-яЁё]/.test(w) && !/^(Wilo|Korf|LG|cookie|IP)/i.test(w)) err(`${where}: смесь латиницы и кириллицы в «${w}»`);
    }
    if (/  +/.test(s)) err(`${where}: двойной пробел в «${s.slice(0, 50)}»`);
    if (/\s[,.;:!?]/.test(s)) warn(`${where}: пробел перед знаком в «${s.slice(0, 50)}»`);
    if (/ - /.test(s)) err(`${where}: дефис вместо тире в «${s.slice(0, 50)}»`);
    if (/"/.test(s) && !isLegal) err(`${where}: прямые кавычки в «${s.slice(0, 50)}»`);
    if (s !== s.trim()) err(`${where}: пробелы по краям «${s.slice(0, 40)}»`);
    if (!isLegal && /\[[^\]]+\]/.test(s)) err(`${where}: заглушка в тексте «${s.slice(0, 50)}»`);
    const nums = s.replace(normRef, '').match(/\d[\d\s]*\d|\d/g);
    if (nums && !isLegal) nums.forEach((n) => digits.set(`${where}: ${s.slice(0, 60)}`, n));
    for (const sent of s.split(/(?<=[.!?])\s+/)) if (sent.split(/\s+/).length > 34) warn(`${where}: длинное предложение (${sent.split(/\s+/).length} слов): «${sent.slice(0, 60)}…»`);
  }
}
for (const [k, v] of digits) warn(`цифры для проверки — ${k} [${v}]`);

// 3. структура и ссылки
for (const s of c.services) {
  for (const k of ['situations', 'scopeGroups', 'inputs', 'check', 'steps', 'outputs', 'factors', 'faq', 'related']) if (!s[k]?.length) err(`/uslugi/${s.slug}/: пусто ${k}`);
  if (s.faq.length < 4) warn(`/uslugi/${s.slug}/: мало вопросов (${s.faq.length})`);
  for (const r of s.related) if (!known.has(r)) err(`/uslugi/${s.slug}/: битая ссылка ${r}`);
  if (s.todo) warn(`/uslugi/${s.slug}/: TODO — ${s.todo}`);
  if (!s.boundary) err(`/uslugi/${s.slug}/: нет границ ответственности`);
}
for (const d of c.directions) {
  for (const k of ['scopeGroups', 'inputs', 'faq', 'related', 'approvers', 'situations', 'steps', 'norms', 'pitfalls', 'outputs']) if (!d[k] || (Array.isArray(d[k]) && !d[k].length)) err(`/napravleniya/${d.slug}/: пусто ${k}`);
  for (const k of ['steps', 'norms', 'pitfalls']) for (const x of d[k] ?? []) if (!x.t || !x.d) err(`/napravleniya/${d.slug}/: в ${k} элемент без t или d`);
  if ((d.faq?.length ?? 0) < 6) warn(`/napravleniya/${d.slug}/: мало вопросов (${d.faq?.length ?? 0}, нужно 6–8)`);
  if (d.norms && (d.norms.length < 4 || d.norms.length > 7)) warn(`/napravleniya/${d.slug}/: нормативов ${d.norms.length} (ориентир 4–7)`);
  if (d.situations && (d.situations.length < 5 || d.situations.length > 6)) warn(`/napravleniya/${d.slug}/: ситуаций ${d.situations.length} (ориентир 5–6)`);
  for (const r of d.related) if (!known.has(r)) err(`/napravleniya/${d.slug}/: битая ссылка ${r}`);
  if (d.todo) warn(`/napravleniya/${d.slug}/: TODO — ${d.todo}`);
}
// статьи базы знаний
const articleChars = (a) => strings([a.lead, a.sections, a.faq]).join(' ').replace(/\u00a0/g, ' ').length;
for (const a of c.articles) {
  const at = `/baza-znaniy/${a.slug}/`;
  for (const k of ['lead', 'updated', 'readMin', 'sections', 'faq', 'related']) if (!a[k] || (Array.isArray(a[k]) && !a[k].length)) err(`${at}: пусто ${k}`);
  if (a.updated && !/^\d{4}-\d{2}-\d{2}$/.test(a.updated)) err(`${at}: updated не в формате ГГГГ-ММ-ДД`);
  for (const [i, sec] of (a.sections ?? []).entries()) if (!sec.h || !(sec.p?.length || sec.list?.length)) err(`${at}: раздел ${i + 1} без заголовка или текста`);
  const n = articleChars(a);
  if (n < 5000 || n > 9000) err(`${at}: объём ${n} знаков (нужно 5–9 тыс.)`);
  if ((a.faq?.length ?? 0) < 3) warn(`${at}: мало вопросов (${a.faq?.length ?? 0})`);
  for (const r of a.related ?? []) if (!known.has(r)) err(`${at}: битая ссылка ${r}`);
}

// дубли вопросов
const q = new Map();
for (const p of pages) for (const f of p.faq ?? []) {
  const key = f.q.toLowerCase();
  if (q.has(key)) err(`${p.path}: вопрос «${f.q}» уже есть на ${q.get(key)}`);
  q.set(key, p.path);
  if (f.a.length < 40) warn(`${p.path}: короткий ответ на «${f.q}»`);
}
// пересечение ответов
const ans = new Map();
for (const p of pages) for (const f of p.faq ?? []) { if (ans.has(f.a)) err(`${p.path}: ответ дублирует ${ans.get(f.a)}`); ans.set(f.a, p.path); }

// кейсы: публикуются только с ролью и разрешениями
for (const k of c.cases) {
  if (!k.role) err(`/proekty/${k.slug}/: не указана роль компании`);
  if (k.role === 'выполнено совместно с партнёром' && !k.partnerNote) err(`/proekty/${k.slug}/: нужна пометка о партнёре`);
  if (!k.permission?.customer) err(`/proekty/${k.slug}/: нет разрешения заказчика`);
  if (k.role === 'выполнено совместно с партнёром' && !k.permission?.partnerMaterials) err(`/proekty/${k.slug}/: нет разрешения на материалы партнёра`);
  if (!k.images?.length) warn(`/proekty/${k.slug}/: нет изображений`);
}
warn(`проекты: опубликовано ${c.cases.length}, черновиков ${c.draftCases.length} (на сайт не попадают)`);

// 4. объём
const words = (x) => strings(x).join(' ').split(/\s+/).length;
const stat = pages.map((p) => `${p.path} — ${words(p)} слов${p.sections ? `, ${articleChars(p)} знаков` : ''}`);

console.log(`Страниц: ${pages.length}\n${stat.join('\n')}\n`);
console.log(`УСЛОВИЯ ПУБЛИКАЦИИ:\n${c.publishGates.map((g, i) => `${i + 1}. ${g}`).join('\n')}\n`);
console.log(`ОШИБКИ (${errors.length}):\n${errors.join('\n') || '—'}\n`);
console.log(`ПРЕДУПРЕЖДЕНИЯ (${warns.length}):\n${warns.join('\n') || '—'}`);
process.exit(errors.length ? 1 : 0);

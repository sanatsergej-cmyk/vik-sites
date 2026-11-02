import * as C from './common.mjs';
import * as S from './services.mjs';
import * as D from './directions.mjs';
import * as P from './pages.mjs';
import * as K from './consultant.mjs';
import * as CS from './cases.mjs';
import * as A from './articles.mjs';

// Типографика: неразрывные пробелы после коротких слов, у чисел, «№», «п.»/«ст.» и перед тире.
const NB = ' ';
const SKIP = new Set(['id', 'slug', 'icon', 'group']);
function typo(s) {
  if (s.startsWith('/') || s.startsWith('http')) return s;
  return s
    .replace(/ — /g, `${NB}— `)
    .replace(/(^|[\s(«—])([вксуоиаВКСУОИА]|на|по|за|из|от|до|об|во|со|ко|не|ни|но|для|при|без) (?=\S)/g, `$1$2${NB}`)
    .replace(/(\d) (?=[А-Яа-яЁёA-Za-z])/g, `$1${NB}`)
    .replace(/№ (?=\d)/g, `№${NB}`)
    .replace(/(^|[\s(])(п|ст|г|гг)\. (?=\d)/g, `$1$2.${NB}`);
}
function deep(x) {
  if (typeof x === 'string') return typo(x);
  if (Array.isArray(x)) return x.map(deep);
  if (x && typeof x === 'object') return Object.fromEntries(Object.entries(x).map(([k, v]) => [k, SKIP.has(k) ? v : deep(v)]));
  return x;
}

export const brand = deep(C.brand);
export const principles = deep(C.principles);
export const cta = deep(C.cta);
export const stages = deep(C.stages);
export const route = deep(C.route);
export const riskPoints = deep(C.riskPoints);
export const form = deep(C.form);
export const faqCommon = deep(C.faqCommon);
export const manufacturers = deep(C.manufacturers);
export const energy = deep(C.energy);
export const mission = deep(C.mission);
export const companyBlock = deep(C.companyBlock);
export const cookie = deep(C.cookie);
export const footer = deep(C.footer);
export const glossary = deep(C.glossary);
export const publishGates = C.publishGates;
export const consultant = deep(K.consultant);
export const cases = deep(CS.cases);
export const draftCases = CS.draftCases;

export const services = deep(S.services);
export const mainServices = services.filter((x) => x.group === 'main');
export const workServices = services.filter((x) => x.group === 'work');
export const extraServices = services.filter((x) => x.group === 'extra');
export const serviceByPath = (path) => services.find((x) => `/uslugi/${x.slug}/` === path);

export const directions = deep(D.directions);
export const directionByPath = (path) => directions.find((x) => `/napravleniya/${x.slug}/` === path);

// База знаний: страницы /baza-znaniy/ и /baza-znaniy/<slug>/ выводят шаблоны (пока не сверстаны).
export const articles = deep(A.articles);
export const articleByPath = (path) => articles.find((x) => `/baza-znaniy/${x.slug}/` === path);
export const knowledgeBase = deep({
  title: 'База знаний по инженерным сетям | ВиК',
  description: 'Статьи о подключении к сетям в Москве и МО: технические условия, вынос сетей, ИТП, исполнительная документация, технический заказчик, исходные данные для сметы.',
  h1: 'База знаний',
  lead: 'Разбираем порядок подключения, согласований и сдачи инженерных сетей по действующим нормам. Ссылки на нормативы сверены на дату обновления статьи.',
});
export const articlePaths = ['/baza-znaniy/', ...articles.map((x) => `/baza-znaniy/${x.slug}/`)];

export const home = deep(P.home);
export const about = deep(P.about);
export const projects = deep(P.projects);
export const documents = deep(P.documents);
export const contacts = deep(P.contacts);
export const notFound = deep(P.notFound);
export const privacy = deep(P.privacy);
export const consent = deep(P.consent);

export const nav = {
  directions: directions.map((x) => ({ label: x.label, href: `/napravleniya/${x.slug}/` })),
  services: mainServices.map((x) => ({ label: x.label, href: `/uslugi/${x.slug}/` })),
  works: workServices.map((x) => ({ label: x.label, href: `/uslugi/${x.slug}/` })),
  extras: extraServices.map((x) => ({ label: x.label, href: `/uslugi/${x.slug}/` })),
  knowledge: { label: 'База знаний', href: '/baza-znaniy/' },
  articles: articles.map((x) => ({ label: x.h1, href: `/baza-znaniy/${x.slug}/` })),
};

export const allPaths = [
  '/',
  ...directions.map((x) => `/napravleniya/${x.slug}/`),
  ...services.map((x) => `/uslugi/${x.slug}/`),
  '/proekty/', ...cases.map((x) => `/proekty/${x.slug}/`), '/o-kompanii/', '/dokumenty/', '/kontakty/', '/privacy/', '/consent/',
];

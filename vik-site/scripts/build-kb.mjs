// Собирает базу знаний консультанта из утверждённых текстов сайта. Запуск: node scripts/build-kb.mjs
import { writeFileSync } from 'node:fs';
import * as c from '../src/content/index.mjs';

const clean = (s) => s.replace(/ /g, ' ').replace(/\s+/g, ' ').trim();
const kb = [];
const add = (title, text, url) => kb.push({ title: clean(title), text: clean(text), url });
const list = (a) => a.join('; ');

for (const s of c.services) {
  const url = `/uslugi/${s.slug}/`;
  const scope = s.scopeGroups.map((g) => `${g.title}: ${list(g.items)}`).join('. ');
  add(`${s.label}: что это и что входит`, `${s.lead} ${scope}.`, url);
  add(`${s.label}: что нужно для оценки`, `${list(s.inputs)}. Если документов нет, достаточно описания задачи.`, url);
  add(`${s.label}: что вы получите`, list(s.outputs), url);
  add(`${s.label}: от чего зависят сроки и стоимость`, `${list(s.factors)}. ${c.consultant.priceNote}`, url);
  add(`${s.label}: границы ответственности`, s.boundary, url);
  for (const f of s.faq) add(f.q, f.a, url);
  for (const x of s.extra ?? []) add(`${s.label}: ${x.title}`, `${list(x.items)}. ${x.note ?? ''}`, url);
}
for (const d of c.directions) {
  const url = `/napravleniya/${d.slug}/`;
  const scope = d.scopeGroups.map((g) => `${g.title}: ${list(g.items)}`).join('. ');
  add(`${d.label}: что входит`, `${d.lead} ${scope}.`, url);
  add(`${d.label}: что нужно для оценки`, list(d.inputs), url);
  add(`${d.label}: ${d.approvers.title}`, d.approvers.text, url);
  if (d.situations?.length) add(`${d.label}: когда к нам обращаются`, list(d.situations), url);
  if (d.steps?.length) add(`${d.label}: этапы работ`, d.steps.map((x) => `${x.t}: ${x.d}`).join(' '), url);
  if (d.norms?.length) add(`${d.label}: нормативные документы`, d.norms.map((x) => `${x.t} — ${x.d}`).join('; '), url);
  if (d.pitfalls?.length) add(`${d.label}: частые ошибки и как их избежать`, d.pitfalls.map((x) => `${x.t}. ${x.d}`).join(' '), url);
  if (d.outputs?.length) add(`${d.label}: что вы получите`, list(d.outputs), url);
  for (const f of d.faq) add(f.q, f.a, url);
}
// база знаний: по записи на раздел статьи и на каждый вопрос
for (const a of c.articles ?? []) {
  const url = `/baza-znaniy/${a.slug}/`;
  add(a.h1, `${a.lead}`, url);
  for (const sec of a.sections) add(`${a.h1}: ${sec.h}`, `${(sec.p ?? []).join(' ')} ${sec.list?.length ? list(sec.list) + '.' : ''}`, url);
  for (const f of a.faq) add(f.q, f.a, url);
}
for (const k of c.cases) add(`Проект: ${k.title}`, `${k.task} Роль: ${k.role}. ${k.scope.join('; ')}.`, `/proekty/${k.slug}/`);
for (const f of c.faqCommon) add(f.q, f.a, '/kontakty/');
for (const g of c.glossary) add(`Что такое ${g.t}`, `${g.t} — ${g.d}.`, '/o-kompanii/');
add('Кто выполняет работы: бригады, партнёры, субподрядчики', c.about.partners.text, '/o-kompanii/');
add('География работ', c.about.geography.text, '/o-kompanii/');
add('Как мы работаем', c.about.how.items.map((i) => `${i.t}: ${i.d}`).join(' '), '/o-kompanii/');
add('Как передать ТУ, проект или документы', `${c.form.text} Первичная оценка занимает от 2 часов до суток в рабочие дни.`, '/kontakty/');

// дубли по заголовку не нужны
const seen = new Set();
const out = kb.filter((e) => (seen.has(e.title + e.url) ? false : seen.add(e.title + e.url)));
writeFileSync(new URL('../public/kb.json', import.meta.url), JSON.stringify(out));
console.log(`kb.json: ${out.length} записей`);

# Изменения контента 01.11.2026

Единый источник текстов: `src/content/`. Импортируйте всё только из `src/content/index.mjs`: там к строкам применяется типографика.

## 1. Направления (`directions`): новые поля

У всех 5 направлений заполнены поля ниже. Старые поля сохранены, `faq` расширен до 6–7 вопросов.

| Поле | Формат | Как выводить |
|---|---|---|
| `situations` | `string[]`, 5–6 шт. | «Когда к нам обращаются», как у услуг |
| `steps` | `{ t, d }[]`, 5–6 шт. `t` — этап, `d` — что делаем и какой результат | Маршрут, нумерация по порядку |
| `norms` | `{ t, d }[]`, 4–6 шт. `t` — реквизиты (`'СП 124.13330.2012'`, `'ПП РФ от 30.11.2021 № 2115'`), `d` — название | Список или таблица «Нормативы». Подпись мелким текстом: «Сверено на 01.11.2026» |
| `pitfalls` | `{ t, d }[]`, 4–5 шт. `t` — частая ошибка, `d` — как её избегаем | Блок «Частые ошибки и как их избегаем» |
| `outputs` | `string[]` | «Что вы получите», как у услуг |

## 2. Новые услуги (`services`, `group: 'extra'`)

- `/uslugi/tekhprisoedinenie-i-tu/` — «Технологическое присоединение и ТУ», иконка `route`
- `/uslugi/vynos-setey/` — «Вынос и переустройство сетей», иконка `layers`
- `/uslugi/ekspertiza/` — «Экспертиза проектной документации», иконка `remarks`

Структура та же, что у 9 существующих услуг. Страницы уже генерирует `uslugi/[slug].astro`. Но там `groupLabel` для `'extra'` сейчас падает в «Основные работы» и `/#raboty`: нужна своя подпись, например «Дополнительные услуги».

Новые экспорты в `index.mjs`: `extraServices`, `nav.extras`.

## 3. База знаний

`articles` (из `articles.mjs`, с типографикой), `articleByPath(path)`, `knowledgeBase` (`title`, `description`, `h1`, `lead` для `/baza-znaniy/`), `articlePaths` (в `allPaths` не включены, пока страниц нет). `nav.knowledge = { label, href: '/baza-znaniy/' }`, `nav.articles = [{ label, href }]`.

Формат статьи:
```
{ slug, title, description, h1, lead, updated: '2026-11-01', readMin: 7,
  sections: [{ h, p: string[], list?: string[] }],   // сначала p, потом list
  faq: [{ q, a }], related: ['/uslugi/…/', '/napravleniya/…/'] }
```
Нужны страницы `src/pages/baza-znaniy/index.astro` и `[slug].astro`. Разметка: `Article` + `FAQPage`, дата из `updated`. Пока их нет, консультант (`public/kb.json`, 85 записей из статей) ссылается на несуществующие адреса.

Статьи (5,2–6,0 тыс. знаков): `tekhnicheskie-usloviya-na-podklyuchenie`, `vynos-setey-iz-pyatna-zastroyki`, `itp-proekt-soglasovanie-dopusk`, `ispolnitelnaya-dokumentatsiya-naruzhnye-seti`, `tekhnicheskiy-zakazchik-i-genpodryadchik`, `iskhodnye-dannye-dlya-smety`.

## 4. Прочее

- `nav` находится в `index.mjs`, а не в `common.mjs`, поэтому дополнен там. В `common.mjs` в `publishGates` добавлена строка о ежегодной сверке нормативов.
- `scripts/check-content.mjs` теперь проверяет новые поля направлений, статьи (мета, объём 5–9 тыс. знаков, ссылки) и запреты «наш объект», 44/223-ФЗ, ГРП/ГРПШ/ГПА, а на странице газа ещё и давления. Реквизиты нормативов (СП, ГОСТ, №, даты) больше не попадают в предупреждения «цифры для проверки». Сроки и количества («от 2 часов») по-прежнему попадают.
- `scripts/build-kb.mjs` добавляет в базу консультанта новые поля направлений и статьи.

## 5. Источники по нормам (проверены 01.11.2026)

Всё, что не удалось подтвердить, в тексты не вошло.

- ГрК РФ ст. 52.1 (ТУ бесплатно, семь рабочих дней, срок действия от трёх лет): consultant.ru/document/cons_doc_LAW_51040/38b3f131482e11c9beba5511be5d68625d177d69/
- ГрК РФ п. 22 ст. 1, ст. 49, ст. 53; ГК РФ ст. 706, 740: consultant.ru/document/cons_doc_LAW_51040/
- ПП РФ № 2130 (вода; действует до 01.03.2028): consultant.ru/document/cons_doc_LAW_402008/
- ПП РФ № 2115 (тепло; временное разрешение и разрешение энергонадзора до акта о подключении): consultant.ru/document/cons_doc_LAW_401940/ ; mos.ru/pgu2/landing/113750709
- ПП РФ № 861 (электро; ТУ как часть договора, акт об осуществлении ТП): base.garant.ru/187740/
- ПП РФ № 1547 (газ; до 18.10.2027): base.garant.ru/402805164/
- ПП РФ № 1034 (учёт тепла, ввод узла учёта): consultant.ru/document/cons_doc_LAW_154646/
- ПП РФ № 87 (до 01.09.2028): consultant.ru/document/cons_doc_LAW_75048/
- ПП РФ № 145 (п. 31: оперативные изменения не позднее чем за 10 рабочих дней; повторная экспертиза): normativ.kontur.ru/document?moduleId=1&documentId=472588 ; письмо Минстроя № 5991-ОД/08: consultant.ru/document/cons_doc_LAW_346495/
- ПП РФ № 272 (негосударственная экспертиза): base.garant.ru/70163138/
- Приказ Минстроя № 344/пр (исполнительная документация, до 01.09.2029): base.garant.ru/406969808/
- Приказ Минстроя № 1026/пр (общий журнал, с 01.09.2023): base.garant.ru/406064781/
- Приказ Минстроя № 421/пр (ред. 30.01.2026): normativ.kontur.ru/document?moduleId=1&documentId=504329
- Приказ Минэнерго № 811 (ПТЭЭП): base.garant.ru/405399745/
- СП 124.13330.2012 (изм. № 5 от 28.11.2025): docs.cntd.ru/document/1200095545
- СП 510.1325800.2022: protect.gost.ru/sp/details/e6b363b3-4682-45dc-9258-c165ca7943a3
- СП 60.13330.2020: gostinfo.ru/catalog/Details/?id=6845508
- СП 7.13130.2013 (изм. № 3 с 01.07.2025): protect.gost.ru/sp/details/78247e24-7498-426f-991f-83d320a7c0bc
- СП 73.13330.2016: protect.gost.ru/sp/changesdetails/b595a91d-d798-4c82-9345-8419ea696528
- СП 31.13330.2021, СП 129.13330.2019: gostinfo.ru/catalog/Details/?id=6895263 ; docs.cntd.ru/document/565256600
- СП 30.13330.2020: gostinfo.ru/catalog/Details/?id=7524344
- СП 32.13330.2018, ГОСТ 34060-2017, ФЗ № 416-ФЗ, № 190-ФЗ, № 69-ФЗ, ПП РФ № 870: действующие. Новых редакций или замен при проверке не найдено (docs.cntd.ru).
- СП 62.13330.2011*: docs.cntd.ru/document/1200084535
- СП 256.1325800.2016 (изм. № 9 от 25.12.2025), СП 76.13330.2016: protect.gost.ru/sp/details/27f20b47-7456-496e-9e1d-8011ddb4a956 ; protect.gost.ru/sp/details/e7468d76-0b61-4d89-b386-c3b2682caee5
- СП 47.13330.2016: normativ.kontur.ru/document?moduleId=9&documentId=431696
- ГОСТ Р 51872-2024 (с 01.11.2024): docs.cntd.ru/document/1310017739
- Москва: единая заявка на mos.ru (с 20.12.2018), mosvodokanal.ru/press/news/8531 ; ордер ОАТИ, ПП Москвы № 284-ПП, docs.cntd.ru/document/537974262 ; сводный план и Мосгоргеотрест, ПП Москвы № 277-ПП, stroimprosto.mos.ru/knowledge/article/mggt/
- Вынос сетей: Россети МР, utp.rossetimr.ru/reorganization/work-reorganization ; Мосводоканал, mosvodokanal.ru/forabonents/connection/ ; МОЭК (СКП, ТЗ на вынос), moek.ru/d/textpage/cb/203/shablon-dogovora-tp.pdf

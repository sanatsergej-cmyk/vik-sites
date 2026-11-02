// Единый источник текстов — ../../vik-site/src/content/ (правит только агент V1). Здесь только реэкспорт, без копий.
export * from '../../../vik-site/src/content/index.mjs';
// Волна 2 (01.11.2026): база знаний и новые услуги. Покрыты `export *` выше, перечислены явно для наглядности.
export {
  articles, articleByPath, knowledgeBase, articlePaths, extraServices, mainServices, workServices, nav,
} from '../../../vik-site/src/content/index.mjs';
export { clients } from '../../../vik-site/src/content/clients.mjs';
export { photos, photosNote } from '../../../vik-site/src/content/photos.mjs';

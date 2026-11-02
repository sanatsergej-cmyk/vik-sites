import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

const indexing = process.env.ENABLE_PUBLIC_INDEXING === '1';

// Вариант V2 «Прогрессив из КП». Тексты импортируются из ../../vik-site/src/content (не копируются),
// поэтому Vite разрешено читать файлы выше корня проекта.
export default defineConfig({
  site: process.env.SITE_URL || 'https://vik.invalid',
  trailingSlash: 'always',
  build: { format: 'directory' },
  integrations: indexing ? [sitemap()] : [],
  // cacheDir локальный, чтобы не трогать кэш Vite в общей node_modules (симлинк на vik-site).
  vite: { cacheDir: '.vite-cache', server: { fs: { allow: ['..', '../..'] } } },
});

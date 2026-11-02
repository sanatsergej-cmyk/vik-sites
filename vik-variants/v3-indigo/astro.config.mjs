import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// V3 «Индиго-инженерия». Тексты импортируются из ../../vik-site/src/content (не копируются),
// поэтому Vite разрешено читать файлы на уровень и два уровня выше корня проекта.
const indexing = process.env.ENABLE_PUBLIC_INDEXING === '1';

export default defineConfig({
  site: process.env.SITE_URL || 'https://vik.invalid',
  trailingSlash: 'always',
  build: { format: 'directory' },
  integrations: indexing ? [sitemap()] : [],
  vite: { server: { fs: { allow: ['..', '../..'] } } },
});

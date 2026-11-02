import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

const indexing = process.env.ENABLE_PUBLIC_INDEXING === '1';

export default defineConfig({
  site: process.env.SITE_URL || 'https://vik.invalid',
  trailingSlash: 'always',
  build: { format: 'directory' },
  integrations: indexing ? [sitemap()] : [],
});

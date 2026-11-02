import { indexing } from '../data/site';

export const GET = ({ site }: { site?: URL }) => {
  const base = (site?.toString() ?? '').replace(/\/$/, '');
  const body = indexing
    ? `User-agent: *\nAllow: /\n\nSitemap: ${base}/sitemap-index.xml\n`
    : 'User-agent: *\nDisallow: /\n';
  return new Response(body, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
};

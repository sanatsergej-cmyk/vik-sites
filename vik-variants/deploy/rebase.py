"""Переписывает абсолютные пути собранного сайта под подпапку (GitHub Pages без своего домена).

python3 rebase.py <dist-копия> /vik-gold
Меняет "/uslugi/…", "/_astro/…", "/kb.json" и т. п. на "/vik-gold/uslugi/…" во всех html/css/js/json/svg,
а также href="/" на href="/vik-gold/". Внешние ссылки и "//" не трогает.
"""
import os
import re
import sys

root, base = sys.argv[1], sys.argv[2].rstrip('/')
names = sorted({n.split('.')[0] if n.endswith(('.json', '.svg', '.txt', '.xml', '.ico', '.html')) and n != '404.html' else n
                for n in os.listdir(root) if not n.startswith('.') and n != 'CNAME'}, key=len, reverse=True)
names = [re.escape(n) for n in names if n]
seg = '|'.join(names)
# путь начинается после кавычки, скобки, пробела, '=' или ',' (srcset); дальше — один из корневых элементов dist
rx = re.compile(r'(?<=["\'(\s=,`])/(?:' + seg + r')(?=[/"\'?#)\s.,`]|$)')
root_href = re.compile(r'((?:href|action)=["\'])/(["\'#?])')

changed = 0
for dp, _, fs in os.walk(root):
    for f in fs:
        if not f.endswith(('.html', '.css', '.js', '.mjs', '.json', '.svg', '.webmanifest', '.txt', '.xml')):
            continue
        p = os.path.join(dp, f)
        s = open(p, encoding='utf-8', errors='ignore').read()
        t = rx.sub(lambda m: base + m.group(0), s)
        t = root_href.sub(lambda m: m.group(1) + base + '/' + m.group(2), t)
        if f == 'robots.txt':
            t = s  # robots.txt на подпапке не действует, оставляем как есть
        if t != s:
            open(p, 'w', encoding='utf-8').write(t)
            changed += 1
print(f'rebase {base}: файлов изменено {changed}')

"""Rebuild the frozen, offline presentation using only Python standard library."""
from pathlib import Path
import base64
import re
root = Path(__file__).resolve().parent
html = (root / 'index.html').read_text()
html = html.replace('<link rel="stylesheet" href="deck.css">', '<style>' + (root / 'deck.css').read_text() + '</style>')
for name in ['graph-data.js', 'deck.js']:
    code = (root / name).read_text().replace('</script', '<\\/script')
    html = html.replace(f'<script src="{name}"></script>', '<script>' + code + '</script>')
for name in sorted(set(re.findall(r'assets/([A-Za-z0-9_.-]+)', html))):
    data = base64.b64encode((root / 'assets' / name).read_bytes()).decode()
    mime = 'image/svg+xml' if name.endswith('.svg') else 'image/png'
    html = html.replace('assets/' + name, 'data:' + mime + ';base64,' + data)
(root / 'PRIOR.html').write_text(html)
print('Built PRIOR.html')

"""Embed common document styling into mapped sources and published copies.
Run after copying a document into the deployment checkout; HTML stays standalone.
Does not overwrite source content from site variants or change application scripts.
"""
from pathlib import Path
import re, json, hashlib

ROOT=Path(__file__).resolve().parent.parent
SITE=ROOT/'.tmp_artifact/rsna-deploy'
CSS=(ROOT/'site/mai-document-theme.css').read_text(encoding='utf-8')
NAV=(ROOT/'site/mai-navigation-theme.css').read_text(encoding='utf-8')
INDEX=SITE/'index.html'
index=INDEX.read_text(encoding='utf-8')
pages=set(re.findall(r'data-src="([^"#]+)',index))
mapping={}
for line in (ROOT/'site/사이트메뉴_원본대응표.md').read_text(encoding='utf-8').splitlines():
    if not line.startswith('|'):continue
    values=re.findall(r'`([^`]+)`',line)
    names=[x for x in values if x.endswith('.html') and '/' not in x]
    sources=[x for x in values if x.startswith('docs/') and x.endswith('.html')]
    if names and sources:mapping[names[0]]=sources[0]

def strip_theme(s):
    s=re.sub(r'\n?<!-- MAI-THEME:START -->.*?<!-- MAI-THEME:END -->\n?','',s,flags=re.S)
    return re.sub(r' data-mai-kind="[^"]+"','',s)

report=[]
def apply(p,kind,nav=False):
    if not p.exists():raise FileNotFoundError(p)
    before=p.read_text(encoding='utf-8')
    clean=strip_theme(before)
    if not re.search(r'</head\s*>',clean,re.I):
        # Legacy QA is an HTML fragment with no encoding declaration.
        # Wrap it without changing any of its existing content or scripts.
        split=clean.index('</style>')+len('</style>')
        clean='<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+clean[:split]+'</head><body>'+clean[split:]+'</body></html>'
    # Whitespace-independent integrity check protects every script, label and table.
    s=re.sub(r'<body\b', '<body data-mai-kind="'+kind+'"',clean,count=1,flags=re.I)
    block='\n<!-- MAI-THEME:START -->\n<style id="mai-document-theme">\n'+CSS+('\n'+NAV if nav else '')+'\n</style>\n<!-- MAI-THEME:END -->\n'
    s=re.sub(r'</head\s*>',lambda m:block+m[0],s,count=1,flags=re.I)
    assert 'id="mai-document-theme"' in s,p
    assert re.sub(r'\s+','',strip_theme(s))==re.sub(r'\s+','',clean),p
    if s!=before:p.write_text(s,encoding='utf-8')
    report.append({'file':str(p.relative_to(ROOT)),'kind':kind,'content_and_scripts':'unchanged'})

seen=set()
for name in sorted(pages):
    kind='app' if name in ['prototype.html','meal-time-ux-demo.html'] else 'document'
    apply(SITE/name,kind)
    if name in mapping:
        p=ROOT/mapping[name]
        if p not in seen:apply(p,kind);seen.add(p)
apply(INDEX,'navigation',True)
(ROOT/'.tmp_artifact/theme-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'{len(pages)} site pages + navigation; {len(seen)} canonical sources. Text, tables and scripts unchanged.')

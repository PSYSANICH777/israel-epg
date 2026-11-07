# Ищет похожие названия для каналов без программы во всех источниках
import sys, re, json, gzip, os, difflib, collections, urllib.request
import xml.etree.ElementTree as ET
def norm(s): return ''.join(ch for ch in s.lower() if ch.isalnum())
un = json.load(urllib.request.urlopen('https://github.com/PSYSANICH777/israel-epg/releases/download/latest/my_report.json'))['unmatched']
names = collections.defaultdict(set)   # norm -> {(src, display, nprog)}
for arg in sys.argv[1:]:
    label, path = arg.split('|')
    if not os.path.exists(path): continue
    head = open(path, 'rb').read(2)
    fh = gzip.open(path) if head == b'\x1f\x8b' else open(path, 'rb')
    disp = {}; cnt = collections.Counter()
    try:
        for ev, el in ET.iterparse(fh, events=('end',)):
            if el.tag == 'channel':
                disp[el.get('id')] = [d.text.strip() for d in el.findall('display-name') if d.text]; el.clear()
            elif el.tag == 'programme': cnt[el.get('channel')] += 1; el.clear()
    except Exception as e: print('ERR', label, e)
    for cid, ds in disp.items():
        if cnt[cid] == 0: continue
        for d in ds: names[norm(d)].add((label, d, cnt[cid]))
keys = list(names)
def core(s):
    s = re.sub(r'\([^)]*\)', ' ', s); s = re.sub(r'\b(HD|FHD|UHD|4K|HDR|IL|UA|RU|IN|GR|IT|ES|EE)\b', ' ', s, flags=re.I); return norm(s)
for u in un:
    c = core(u)
    hits = [k for k in keys if c and (c in k or (len(k) > 3 and k in c))][:8]
    hits += difflib.get_close_matches(c, keys, n=5, cutoff=0.75)
    out = []
    for k in dict.fromkeys(hits):
        for (l, d, n) in sorted(names[k])[:2]: out.append(f'{d} [{l}, {n}]')
    print('CAND', u, '=>', ' | '.join(out[:8]) if out else '-')

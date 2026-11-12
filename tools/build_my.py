# Собирает my.xml.gz: программа для каждого канала плейлиста, название канала = как в плейлисте
import sys, os, re, json, gzip, time, datetime, collections
import xml.etree.ElementTree as ET

NOW = time.time()
FROM, TO = NOW - 8 * 86400, NOW + 4 * 86400

def norm(s): return ''.join(ch for ch in s.lower() if ch.isalnum())
TAILS = set("hd fhd uhd 4k 8k sd hdr hevc ua il by kz ru old orig ee in am ge az uz md lt lv eu tr us uk int + 50 fps tv".split())
def base(s):
    t = re.sub(r'\([^)]*\)|\[[^\]]*\]', ' ', s).strip()
    t = re.sub(r'^[A-Z]{2,3} - ', '', t)
    w = t.split()
    while len(w) > 1 and w[-1].lower().rstrip('.') in TAILS: w.pop()
    return norm(' '.join(w))
def stripq(n): return re.sub(r'(uhd|fhd|hd|4k|sd|hdr|ua|il|by|kz|ru)+$', '', n)

ALI = {k: [norm(x) for x in v] for k, v in json.load(open('tools/aliases.json', encoding='utf-8')).items()}
PL = json.load(open('tools/playlist.json', encoding='utf-8'))
# каналы из шаблона it999 (плейлист Edem по ключу) — добавляем их названия тоже
if os.path.exists('src/edem_tpl.m3u'):
    have = {c['name'] for c in PL}; grp = ''
    for line in open('src/edem_tpl.m3u', encoding='utf-8', errors='replace'):
        if line.startswith('#EXTINF'):
            m = re.search(r'group-title="([^"]*)"', line); grp = m.group(1) if m else ''
            nm = line.split(',', 1)[1].strip() if ',' in line else ''
            if nm and nm not in have and grp.lower() != 'взрослые': PL.append({'name': nm, 'group': grp}); have.add(nm)
    print('PL with template', len(PL))

def is_il(c): return 'Израил' in c['group'] or re.search(r'\sIL$', c['name'].strip(), re.I) is not None
def keys_for(c):
    n = norm(c['name']); b = base(c['name'])
    out = [n, stripq(n), b]
    if '+' in c['name']:
        bp = base(c['name'].replace('+', ' plus ')); out.insert(0, bp); out += ALI.get(bp, [])
    out += ALI.get(b, [])
    seen = []; [seen.append(k) for k in out if k and k not in seen]
    return seen

def ts(s):
    s = s.strip(); dt = datetime.datetime.strptime(s[:14], '%Y%m%d%H%M%S'); off = 0
    if len(s) > 15:
        z = s[15:].strip()
        if len(z) >= 5: off = (-1 if z[0] == '-' else 1) * (int(z[1:3]) * 60 + int(z[3:5]))
    return (dt - datetime.datetime(1970, 1, 1)).total_seconds() - off * 60

wanted = set()
for c in PL: wanted.update(keys_for(c))

# источники: (метка, файл, израильский?)
SOURCES = [l.split('|') for l in sys.argv[1:]]
index = collections.defaultdict(list)   # key -> [(src, cid)]
progs = {}                               # (src, cid) -> list[(start, stop, startstr, stopstr, title)]
icons = {}                               # (src, cid) -> url
for si, (label, path, il) in enumerate(SOURCES):
    if not os.path.exists(path) or os.path.getsize(path) < 100: print('SKIP', label); continue
    f = open(path, 'rb'); head = f.read(2); f.close()
    fh = gzip.open(path, 'rb') if head == b'\x1f\x8b' else open(path, 'rb')
    keep = set(); nch = 0; npr = 0
    try:
        for ev, el in ET.iterparse(fh, events=('end',)):
            if el.tag == 'channel':
                nch += 1; cid = el.get('id')
                for d in el.findall('display-name'):
                    if not d.text: continue
                    for k in {norm(d.text), base(d.text)}:
                        if k in wanted: index[k].append((si, cid)); keep.add(cid)
                if cid in keep:
                    ic = el.find('icon')
                    if ic is not None and ic.get('src', '').startswith('http'): icons[(si, cid)] = ic.get('src')
                el.clear()
            elif el.tag == 'programme':
                cid = el.get('channel')
                if cid in keep:
                    try:
                        a, z = ts(el.get('start')), ts(el.get('stop'))
                        if z > FROM and a < TO:
                            t = el.findtext('title') or ''
                            progs.setdefault((si, cid), []).append((a, z, el.get('start'), el.get('stop'), t.strip()))
                            npr += 1
                    except Exception: pass
                el.clear()
    except Exception as e: print('PARSE ERROR', label, repr(e)[:150])
    print('SRC', label, 'channels', nch, 'kept', len(keep), 'programmes', npr)

def score(c, cand, rank):
    si, cid = cand
    lst = progs.get(cand, [])
    if not lst: return None
    cur = any(a <= NOW < z for a, z, *_ in lst)
    ilsrc = SOURCES[si][2] == '1'
    return ((ilsrc if is_il(c) else True), cur, len(lst), -rank)

root = ET.Element('tv', {'generator-info-name': 'my-epg'})
nicons = [0]
chosen = collections.Counter(); unmatched = []; out_progs = []
used = set()
for c in PL:
    cid_out = c['name']
    if cid_out in used: continue
    used.add(cid_out)
    best = None; icon = None
    for rank, k in enumerate(keys_for(c)):
        for cand in index.get(k, []):
            if icon is None and cand in icons: icon = icons[cand]
            sc = score(c, cand, rank)
            if sc and (best is None or sc > best[0]): best = (sc, cand)
    if not best: unmatched.append(c['name']); continue
    chosen[SOURCES[best[1][0]][0]] += 1
    icon = icons.get(best[1], icon)
    ch = ET.SubElement(root, 'channel', {'id': cid_out}); ET.SubElement(ch, 'display-name').text = c['name']
    if icon: ET.SubElement(ch, 'icon', {'src': icon}); nicons[0] += 1
    seen = set()
    for a, z, s1, s2, t in sorted(progs[best[1]]):
        if s1[:14] in seen: continue
        seen.add(s1[:14]); out_progs.append((cid_out, s1, s2, t, a))

# прошлые передачи из предыдущей версии (архив)
kept = 0
if os.path.exists('old_my.xml.gz'):
    first = {}
    for cid, s1, s2, t, a in out_progs: first[cid] = min(first.get(cid, a), a)
    try:
        for ev, el in ET.iterparse(gzip.open('old_my.xml.gz'), events=('end',)):
            if el.tag == 'programme':
                cid = el.get('channel')
                if cid in first:
                    a, z = ts(el.get('start')), ts(el.get('stop'))
                    if z > FROM and a < first[cid]:
                        out_progs.append((cid, el.get('start'), el.get('stop'), el.findtext('title') or '', a)); kept += 1
                el.clear()
    except Exception as e: print('old unreadable', e)
for cid, s1, s2, t, a in sorted(out_progs, key=lambda x: (x[0], x[4])):
    p = ET.SubElement(root, 'programme', {'start': s1, 'stop': s2, 'channel': cid}); ET.SubElement(p, 'title').text = t
data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
with gzip.open('my.xml.gz', 'wb', 9) as g: g.write(data)
print('RESULT matched', len(PL) - len(unmatched), 'of', len(PL), 'programmes', len(out_progs), 'kept old', kept, 'size', os.path.getsize('my.xml.gz'))
print('CHOSEN', dict(chosen), 'icons', nicons[0])
json.dump({'unmatched': unmatched, 'chosen': dict(chosen)}, open('my_report.json', 'w'), ensure_ascii=False, indent=0)
print('UNMATCHED', '; '.join(unmatched))

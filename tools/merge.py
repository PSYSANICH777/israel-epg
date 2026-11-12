# Объединяет свежие файлы с прошлым guide.xml: прошлые передачи (до 8 дней) остаются для архива
import sys, os, time, gzip, datetime
import xml.etree.ElementTree as ET

def ts(s):
    s = s.strip(); dt = datetime.datetime.strptime(s[:14], '%Y%m%d%H%M%S')
    off = 0
    if len(s) > 15:
        z = s[15:].strip(); sg = -1 if z[0] == '-' else 1; off = sg * (int(z[1:3]) * 60 + int(z[3:5]))
    return (dt - datetime.datetime(1970, 1, 1)).total_seconds() - off * 60

out_path, inputs = sys.argv[1], sys.argv[2:]
now = time.time()
channels, progs = {}, {}
newest_min = {}
for p in inputs:
    if not os.path.exists(p) or os.path.getsize(p) < 50: print('skip', p); continue
    r = ET.parse(p).getroot()
    for c in r.findall('channel'): channels.setdefault(c.get('id'), c)
    for pr in r.findall('programme'):
        k = (pr.get('channel'), pr.get('start')[:14]); progs[k] = pr
        st = ts(pr.get('start')); ch = pr.get('channel')
        newest_min[ch] = min(newest_min.get(ch, st), st)
    print('new', p, len(r.findall('channel')), len(r.findall('programme')))
old = out_path
kept = 0
if os.path.exists(old):
    try:
        r = ET.parse(old).getroot()
        for c in r.findall('channel'): channels.setdefault(c.get('id'), c)
        for pr in r.findall('programme'):
            ch = pr.get('channel'); st = ts(pr.get('start')); sp = ts(pr.get('stop'))
            if sp < now - 8 * 86400: continue
            if ch in newest_min and st >= newest_min[ch]: continue
            k = (ch, pr.get('start')[:14])
            if k not in progs: progs[k] = pr; kept += 1
    except Exception as e: print('old guide unreadable', e)
root = ET.Element('tv', {'generator-info-name': 'tv-epg'})
for cid in sorted(channels): root.append(channels[cid])
for k in sorted(progs): root.append(progs[k])
ET.ElementTree(root).write(out_path, encoding='utf-8', xml_declaration=True)
with open(out_path, 'rb') as f, gzip.open(out_path + '.gz', 'wb', 9) as g: g.write(f.read())
print('channels', len(channels), 'programmes', len(progs), 'kept from old', kept)

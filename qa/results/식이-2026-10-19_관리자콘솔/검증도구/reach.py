import json, sys, os, itertools, collections
sys.path.insert(0, os.path.dirname(__file__))
from model import run, GP, AXN
sys.stdout.reconfigure(encoding='utf-8')
OLD = json.load(open('C:/Users/이사라/Downloads/diet-1.1.0.json', encoding='utf-8'))['data']
CH = {i for i, (a, b) in enumerate(zip(OLD['goal_phrases'], GP)) if a['tile_text_ko'] != b['tile_text_ko'] or a['reason_text_ko'] != b['reason_text_ko'] or a['stage_code'] != b['stage_code']}
N = 150
conds = [[], ['HYPERTENSION'], ['DYSLIPIDEMIA'], ['DIABETES'], ['CHRONIC_KIDNEY_DISEASE'], ['HYPERTENSION', 'DYSLIPIDEMIA'], ['HYPERTENSION', 'DIABETES'], ['DIABETES', 'DYSLIPIDEMIA']]
times = ['01:00', '05:00', '08:00', '10:00', '13:00', '15:00', '18:00', '21:00', '23:00']
modes = {'INTRO': (1, False), 'BASE': (3, True), 'CHAL': (1, True)}
hit = collections.Counter()
best = {}
for c, t, (mn, (rot, done)), fx in itertools.product(conds, times, modes.items(), [1, 2]):
    out = run('2026-10-19', c, 'ko', [[t, fx, rot, done] for _ in range(N)])
    s = {o['goal']['pi'] for o in out if o['goal'] and o['goal'].get('pi') is not None}
    for i in s:
        hit[i] += 1
        best.setdefault(i, (c, t, mn, fx))
# also mixed-time week pattern
for c in conds:
    for mn, (rot, done) in modes.items():
        pat = ['08:00', '13:00', '20:00', '13:00', '10:00', '18:00', '23:00']
        out = run('2026-10-19', c, 'ko', [[pat[d % 7], 1, rot, done] for d in range(N)])
        for o in out:
            if o['goal'] and o['goal'].get('pi') is not None:
                hit[o['goal']['pi']] += 1
                best.setdefault(o['goal']['pi'], (c, 'mixed', mn, 1))
allp = [i for i, p in enumerate(GP) if p['pool_type'] != 'LOW_BURDEN']
never = [i for i in allp if i not in hit]
print('phrases total(excl low burden)', len(allp), 'reachable', len(allp) - len(never), 'never', len(never))
print('changed', len(CH), 'reachable', len([i for i in CH if i in hit]))
byax = collections.Counter((GP[i]['pool_type'], AXN.get(GP[i]['axis_key'], '회복'), GP[i]['stage_code']) for i in never)
for k, v in sorted(byax.items(), key=lambda x: str(x)):
    tot = sum(1 for i in allp if (GP[i]['pool_type'], AXN.get(GP[i]['axis_key'], '회복'), GP[i]['stage_code']) == k)
    print(k, f'{v}/{tot} never')
json.dump({'never': never, 'changed': sorted(CH), 'changed_never': sorted(i for i in CH if i not in hit), 'best': {i: best[i] for i in CH if i in best}}, open(os.path.join(os.path.dirname(__file__), 'reach.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('changed never:')
for i in sorted(i for i in CH if i not in hit):
    p = GP[i]
    print(' ', i, AXN.get(p['axis_key'], '회복'), p['stage_code'], p['time_code'], p['tile_text_ko'])

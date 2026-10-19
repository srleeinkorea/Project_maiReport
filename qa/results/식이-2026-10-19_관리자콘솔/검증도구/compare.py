import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from model import run, GP, AXN, AXID, D
sys.stdout.reconfigure(encoding='utf-8')
OLD = json.load(open('C:/Users/이사라/Downloads/diet-1.1.0.json', encoding='utf-8'))['data']
OLDT = set(p['tile_text_ko'] for p in OLD['goal_phrases'])
NEWT = set(p['tile_text_ko'] for p in GP)
CHANGED = {i for i, (a, b) in enumerate(zip(OLD['goal_phrases'], GP)) if a['tile_text_ko'] != b['tile_text_ko'] or a['reason_text_ko'] != b['reason_text_ko'] or a['stage_code'] != b['stage_code']}
IDNAME = {v: AXN[k] for k, v in AXID.items()}

R = lambda n, f: [f(d) for d in range(1, n + 1)]
SCN = {
    'S01_시간대경계': ('2026-10-19', [], 'ko', [[t, 1, 1, True] for t in ['03:00', '04:00', '09:00', '10:00', '11:00', '12:00', '16:00', '17:00', '23:00', '00:00']]),
    'S02_일반13시': ('2026-10-19', [], 'ko', R(8, lambda d: ['13:00', 1, 1, True])),
    'S05_고혈압_단계오르내림': ('2026-10-19', ['HYPERTENSION'], 'ko', R(25, lambda d: ['13:00', 1, 1, not (d in (19, 22))])),
    'S06_고혈압_개선필요상한': ('2026-10-19', ['HYPERTENSION'], 'ko', R(22, lambda d: ['13:00', 1, 3 if d % 3 == 1 else 1, True])),
    'S07_결식_회복문구': ('2026-10-19', [], 'ko', [['13:00', 3, 1, True], ['20:00', 2, 1, True], ['00:00', 2, 1, True], ['08:00', 2, 1, True], ['10:00', 2, 1, True], ['13:00', 2, 1, True], ['13:00', 2, 1, True], ['21:00', 3, 1, True], ['13:00', 3, 1, True], ['20:00', 2, 1, True]]),
    'S08_고혈압_미응답_3일연속': ('2026-10-19', ['HYPERTENSION'], 'ko', R(7, lambda d: ['13:00', 1, None if 2 <= d <= 4 else 1, True])),
    'S09_일반06시_야식': ('2026-10-19', [], 'ko', R(9, lambda d: ['06:00', 1, 1, True])),
    'S10_당뇨': ('2026-10-19', ['DIABETES'], 'ko', R(8, lambda d: ['13:00', 1, 1, True])),
    'S11_신장질환': ('2026-10-19', ['CHRONIC_KIDNEY_DISEASE'], 'ko', R(8, lambda d: ['13:00', 1, 1, True])),
    'S12_이상지질혈증': ('2026-10-19', ['DYSLIPIDEMIA'], 'ko', R(7, lambda d: ['13:00', 1, 1, True])),
    'S13_영어13시': ('2026-10-19', [], 'en', R(7, lambda d: ['13:00', 1, 1, True])),
    'S14_일반20시': ('2026-10-19', [], 'ko', R(9, lambda d: ['20:00', 1, 1, True])),
    'S15_일반08시': ('2026-10-19', [], 'ko', R(9, lambda d: ['08:00', 1, 1, True])),
    'S16_명절주말': ('2027-02-05', [], 'ko', R(4, lambda d: ['13:00', 1, 1, True])),
    'S17_일반15시_오후': ('2026-10-19', [], 'ko', R(8, lambda d: ['15:00', 1, 1, True])),
    'C1_고혈압+이상지질_13시_기본': ('2026-10-19', ['HYPERTENSION', 'DYSLIPIDEMIA'], 'ko', R(100, lambda d: ['13:00', 1, 3, True])),
    'C2_일반_06시_입문유지': ('2026-10-19', [], 'ko', R(100, lambda d: ['06:00', 1, 1, False])),
    'C3_일반_18시_도전': ('2026-10-19', [], 'ko', R(100, lambda d: ['18:00', 1, 1, True])),
    'C4_일반_06시_도전': ('2026-10-19', [], 'ko', R(100, lambda d: ['06:00', 1, 1, True])),
    'C5_일반_18시_입문유지': ('2026-10-19', [], 'ko', R(100, lambda d: ['18:00', 1, 1, False])),
    'C6_일반_06시_기본': ('2026-10-19', [], 'ko', R(100, lambda d: ['06:00', 1, 3, True])),
    'D1_HYPERTENSION_05시_INTRO': ('2026-10-19', ['HYPERTENSION'], 'ko', R(40, lambda d: ['05:00', 1, 1, False])),
    'D2_DIABETES_10시_BASE': ('2026-10-19', ['DIABETES'], 'ko', R(70, lambda d: ['10:00', 1, 3, True])),
    'D3_CHRONIC_KIDNEY_DISEASE_10시_CHAL': ('2026-10-19', ['CHRONIC_KIDNEY_DISEASE'], 'ko', R(70, lambda d: ['10:00', 1, 1, True])),
    'D4_일반_10시_INTRO': ('2026-10-19', [], 'ko', R(40, lambda d: ['10:00', 1, 1, False])),
    'D5_일반_01시_INTRO': ('2026-10-19', [], 'ko', R(40, lambda d: ['01:00', 1, 1, False])),
    'D6_HYPERTENSION_05시_BASE': ('2026-10-19', ['HYPERTENSION'], 'ko', R(40, lambda d: ['05:00', 1, 3, True])),
    'D7_CHRONIC_KIDNEY_DISEASE_10시_INTRO': ('2026-10-19', ['CHRONIC_KIDNEY_DISEASE'], 'ko', R(40, lambda d: ['10:00', 1, 1, False])),
    'D8_HYPERTENSION+DIABETES_05시_INTRO': ('2026-10-19', ['HYPERTENSION', 'DIABETES'], 'ko', R(40, lambda d: ['05:00', 1, 1, False])),
    'D9_DYSLIPIDEMIA_05시_BASE': ('2026-10-19', ['DYSLIPIDEMIA'], 'ko', R(70, lambda d: ['05:00', 1, 3, True])),
    'D10_HYPERTENSION+DIABETES_05시_BASE': ('2026-10-19', ['HYPERTENSION', 'DIABETES'], 'ko', R(70, lambda d: ['05:00', 1, 3, True])),
    'C7_일반_18시_적게먹음': ('2026-10-19', [], 'ko', R(100, lambda d: ['18:00', 2, 1, False])),
}

# parse server results
srv = {}
cur = None
for line in open(os.path.join(os.path.dirname(__file__), '서버_실행결과.txt'), encoding='utf-8').read().splitlines():
    if not line.strip():
        continue
    if line.startswith('#'):
        n, user, start, cond, lang = line[1:].split('|')
        cur = srv.setdefault(n, {'user': user, 'rec': []})
        continue
    f = line.split('|')
    d, sd, t, meal, md = f[:5]
    rest = '|'.join(f[5:])
    # qs ~ separated; fields after qs: snap | goal | opts
    parts = line.split('|')
    # locate snapshot (contains '41:')
    si = next(i for i, x in enumerate(parts) if x.startswith('41:'))
    qs = '|'.join(parts[5:si]).split('~')
    snap = parts[si]
    goal = parts[si + 1]
    opts = '|'.join(parts[si + 2:])
    rot = None
    rstate = None
    for q in qs:
        if q.startswith('R:') and q != 'R:-':
            x = q[2:].split('|')
            rot = None if x[0] == 'null' else x[0]
            rstate = x[2]
    g = None
    if goal != '-':
        ax, pool, st, tx, fc, tm, sel = goal.split('^')
        g = dict(ax=ax, pool=pool, st=st, tx=tx, fc=fc, tm=tm, sel=sel)
    cur['rec'].append(dict(d=int(d), sd=sd, t=t, meal=meal, md=md, qs=qs, rot=rot, rstate=rstate, snap=dict(x.split(':') for x in snap.split(',')), g=g, opts=opts))

SMAP = {'OBSERVING': 'O', 'NEEDS_WORK': 'N', 'NORMAL': 'A', 'GOOD': 'G'}
report = []
hit_changed = set()
total = 0
fails = 0
for n, (start, cond, lang, days) in SCN.items():
    if n not in srv:
        continue
    exp = run(start, cond, lang, days)
    s = srv[n]
    report.append(f'## {n} (가상 사용자 #{s["user"]}, {start}, {"+".join(cond) or "일반"}, {lang})')
    for e, r in zip(exp, s['rec']):
        total += 1
        issues = []
        if e['sd'] != r['sd']:
            issues.append(f'세션날짜 기대 {e["sd"]} 실제 {r["sd"]}')
        if e['meal'] != r['meal'] or e['md'] != r['md']:
            issues.append(f'끼니 기대 {e["md"]} {e["meal"]} 실제 {r["md"]} {r["meal"]}')
        if (e['rot'] or '-') != (r['rot'] or '-'):
            issues.append(f'회전축 기대 {e["rot"]} 실제 {r["rot"]}')
        for k, (st, cnt) in e['snap'].items():
            sv = r['snap'].get(k, '')
            if sv[:1] != SMAP[st]:
                issues.append(f'축상태 {IDNAME[k]} 기대 {st}({cnt}) 실제 {sv}')
        eg = e['goal']
        rg = r['g']
        exp_txt = None
        if eg and eg['pi'] is not None:
            p = GP[eg['pi']]
            exp_txt = p['tile_text_en'] if lang == 'en' else p['tile_text_ko']
        if (exp_txt or '-') != ((rg or {}).get('tx') or '-'):
            issues.append(f'목표 기대 「{exp_txt}」({GP[eg["pi"]]["stage_code"] if exp_txt else ""}) 실제 「{rg and rg["tx"]}」({rg and rg["st"]})')
        if rg:
            # match server phrase in 1.1.1
            cand = [i for i, p in enumerate(GP) if (p['tile_text_en'] if lang == 'en' else p['tile_text_ko']) == rg['tx'] and AXID.get(p['axis_key'], 'None') == (rg['ax'] or 'None') or ((p['tile_text_en'] if lang == 'en' else p['tile_text_ko']) == rg['tx'] and p['pool_type'] == 'RECOVERY' == rg['pool'])]
            if not cand:
                issues.append(f'1.1.1에 없는 목표 문구 「{rg["tx"]}」' + (' (1.1.0 옛 문구)' if rg['tx'] in OLDT else ''))
            else:
                pi = cand[0]
                p = GP[pi]
                if pi in CHANGED:
                    hit_changed.add(pi)
                fc_exp = p['title_text_full_context_en'] if lang == 'en' else p['title_text_full_context_ko']
                if lang == 'ko' and (rg['fc'] or None) != (fc_exp or None):
                    issues.append(f'긴 문장 기대 「{fc_exp}」 실제 「{rg["fc"]}」')
                if (p['stage_code'] or '') != (rg['st'] or '') and rg['pool'] == 'AXIS_STAGE':
                    issues.append(f'단계 표기 데이터 {p["stage_code"]} 실제 {rg["st"]}')
        status = 'OK' if not issues else 'NG'
        if issues:
            fails += 1
        rot_s = f'{r["rot"]}({r["rstate"]})' if r['rot'] else '없음'
        g_s = f'{rg["tx"]} [{rg["pool"]}/{IDNAME.get(rg["ax"], "회복")}/{rg["st"]}]' if rg else '없음'
        report.append(f'- D{r["d"]} {r["sd"]} {r["t"]} {r["meal"]} · 회전 {rot_s} · 목표 {g_s} · {status}' + ('' if not issues else '\n    - ' + '\n    - '.join(issues)))
print(f'TOTAL days {total}, NG {fails}')
print('CHANGED phrases hit:', len(hit_changed), 'of', len(CHANGED))
print('NOT HIT:', sorted(CHANGED - hit_changed))
json.dump(sorted(hit_changed), open(os.path.join(os.path.dirname(__file__), 'hit_changed.json'), 'w'))
open(os.path.join(os.path.dirname(__file__), '날짜별_대조결과.md'), 'w', encoding='utf-8').write('\n'.join(report))

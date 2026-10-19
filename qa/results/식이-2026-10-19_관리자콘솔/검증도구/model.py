import json, sys, datetime as dt, collections
sys.stdout.reconfigure(encoding='utf-8')
D = json.load(open('C:/Users/이사라/Downloads/diet-1.1.1.json', encoding='utf-8'))['data']
AX = {a['axis_key']: a for a in D['axes']}
AXN = {k: a['axis_name_ko'] for k, a in AX.items()}
AXID = {f'axis_key_{i}': str(40 + i) for i in range(1, 9)}
AXORD = sorted(AX, key=lambda k: AX[k]['display_order'])
Q = D['questions']
OPT = collections.defaultdict(list)
for o in D['options']:
    OPT[o['question_key']].append(o)
for k in OPT:
    OPT[k].sort(key=lambda o: o['option_order'])
ROT = [q for q in Q if q['question_role'] == 'ROTATING']
FIXQ = [q for q in Q if q['question_role'] == 'FIXED'][0]
SCORED_AX = set(q['axis_key'] for q in Q if q['is_scored'] and q['axis_key'])
PC = {p['condition_code']: p['rule_key'] for p in D['profile_conditions']}
DAX = collections.defaultdict(set)
for r in D['disease_axes']:
    DAX[r['rule_key']].add(r['axis_key'])
DRULE = {r['rule_key']: r for r in D['disease_rules']}
DBAN = collections.defaultdict(set)
for r in D['disease_bans']:
    DBAN[r['rule_key']].add(r['nature_code'])
CAL = {c['calendar_date']: c['calendar_code'] for c in D['calendar']}
GP = D['goal_phrases']
P = D['policy']
STAGES = ['INTRO', 'BASE', 'CHALLENGE']


def hm(t):
    h, m = map(int, t.split(':')[:2])
    return h * 60 + m


def meal_of(sd, t):
    m = hm(t)
    if m < 240:
        return (sd, 'DINNER', '어제 저녁')
    if m < 600:
        return (sd - dt.timedelta(1), 'DINNER', '어제 저녁')
    if m < 720:
        return (sd, 'BREAKFAST', '오늘 아침')
    if m < 1020:
        return (sd, 'LUNCH', '오늘 점심')
    return (sd, 'DINNER', '오늘 저녁')


def time_ok(p, t, sd, lang):
    m = hm(t)
    tc = p['time_code']
    after_dinner = m >= 1020 or m < 240
    if after_dinner and not p['after_dinner_eligible']:
        return False
    if m < 240 and tc not in ('ANY', 'EVENING'):
        return False
    if 600 <= m < 720 and tc != 'ANY':
        return False
    if tc == 'MORNING_ENTRY' and not (240 <= m < 600):
        return False
    if tc == 'AFTERNOON_ENTRY' and not (720 <= m < 1020):
        return False
    if tc == 'EVENING' and not after_dinner:
        return False
    if tc == 'PRE_MIDNIGHT' and not (1020 <= m < 1440):
        return False
    cc = p['calendar_code']
    wd = sd.weekday()
    if cc == 'WEEKDAY' and wd >= 5:
        return False
    if cc == 'WEEKEND' and wd < 5:
        return False
    if cc == 'HOLIDAY' and CAL.get(sd.isoformat()) != 'HOLIDAY':
        return False
    if cc == 'HOLIDAY_OR_EXTENDED' and sd.isoformat() not in CAL:
        return False
    if lang == 'en' and not p['tile_text_en']:
        return False
    if '과일' in (p['tile_text_ko'] or ''):
        return False
    if p['screening_only']:
        return False
    return True


def rot_time_ok(q, t):
    if not q['entry_start_time']:
        return True
    m = hm(t)
    return hm(q['entry_start_time']) <= m < hm(q['entry_end_time'])


def run(start, cond, lang, days):
    sd = dt.date.fromisoformat(start)
    L = set()
    bans = set()
    for c in cond:
        r = PC[c]
        if DRULE[r]['link_enabled']:
            L |= DAX[r]
        if DRULE[r]['ban_enabled']:
            bans |= DBAN[r]
    answers = []  # (sd, axis, score, qkey, mealkey)
    shown = []    # (sd, axis, state)
    goals = []
    stage = {a: 'INTRO' for a in AX}
    stage_chg = {a: None for a in AX}
    out = []
    for i, (t, fx, rot, done) in enumerate(days):
        if i > 0:
            sd = sd + dt.timedelta(1)
        md, mt, ml = meal_of(sd, t)
        mk = (md, mt)
        snap = {}
        for a in AXORD:
            if a not in SCORED_AX:
                continue
            hist = [x for x in answers if x[1] == a and x[2] is not None and x[0] < sd and (sd - x[0]).days <= P['good_lookback_days']]
            h28 = [x for x in hist if (sd - x[0]).days <= P['observation_days']]
            if len(h28) < P['minimum_answers']:
                st = 'OBSERVING'
            elif sum(x[2] == -1 for x in h28) / len(h28) >= P['bad_ratio_min']:
                st = 'NEEDS_WORK'
            elif len(hist) < P['good_answer_count']:
                st = 'NORMAL'
            else:
                r7 = sorted(hist, key=lambda x: x[0])[-7:]
                g = sum(x[2] == 1 for x in r7) / 7
                b = sum(x[2] == -1 for x in r7) / 7
                st = 'GOOD' if g >= P['good_ratio_min'] and b < P['good_bad_ratio_max'] else 'NORMAL'
            snap[a] = (st, len(h28))
        prev = [x for x in answers if x[3] == FIXQ['question_key'] and x[4] == mk]
        if prev:
            fscore = prev[-1][2]
            freused = True
        else:
            fscore = OPT[FIXQ['question_key']][fx - 1]['score_value']
            freused = False
            answers.append((sd, FIXQ['axis_key'], fscore, FIXQ['question_key'], mk))
        rq = None
        rstate = None
        if fscore != -1:
            cands = [q for q in ROT if rot_time_ok(q, t)]

            def answered_cnt(a):
                return sum(1 for x in answers if x[1] == a and x[3] != FIXQ['question_key'] and x[0] < sd and (sd - x[0]).days <= P['observation_days'])

            def last_shown(a):
                s = [x[0] for x in shown if x[1] == a]
                return max(s) if s else dt.date.min

            def consec(a):
                return all(any(x[1] == a and x[0] == sd - dt.timedelta(k) for x in shown) for k in range(1, P['consecutive_axis_days'] + 1))

            key = lambda q: (answered_cnt(q['axis_key']), last_shown(q['axis_key']), AX[q['axis_key']]['display_order'], q['display_order'])
            turn = cands
            if L:
                done_l = set()
                for x in sorted([x for x in answers if x[3] != FIXQ['question_key'] and x[0] < sd], key=lambda x: x[0]):
                    if x[1] in L:
                        done_l.add(x[1])
                        if done_l >= L and all(q['axis_key'] in L for q in ROT):
                            done_l = set()
                    elif done_l >= L:
                        done_l = set()
                if not done_l >= L:
                    turn = [q for q in cands if q['axis_key'] in L and q['axis_key'] not in done_l]
                else:
                    turn = [q for q in cands if q['axis_key'] not in L]
            t2 = sorted([q for q in turn if not consec(q['axis_key'])], key=key)
            if not t2:
                t2 = sorted([q for q in cands if not consec(q['axis_key'])], key=lambda q: ((q['axis_key'] not in L),) + key(q))
            if t2:
                rq = t2[0]
                prevr = [x for x in answers if x[3] == rq['question_key'] and x[4] == mk]
                if prevr:
                    rstate = 'REUSED'
                elif rot:
                    sc = OPT[rq['question_key']][rot - 1]['score_value']
                    answers.append((sd, rq['axis_key'], sc, rq['question_key'], mk))
                    rstate = 'ANSWERED'
                else:
                    rstate = 'MISSED'
                shown.append((sd, rq['axis_key'], rstate))
        goal = None
        make = fscore == -1 or rq is None or rstate in ('ANSWERED', 'REUSED')
        if make:
            def used_key(pi):
                u = [g['date'] for g in goals if g['pi'] == pi]
                if not u:
                    return (0, dt.date.min)
                last = max(u)
                if (sd - last).days <= P['goal_history_days']:
                    return (1, last)
                return (0, dt.date.min)

            def pick(pool, axis=None, stg=None):
                c = [pi for pi, p in enumerate(GP) if p['pool_type'] == pool and (axis is None or p['axis_key'] == axis)
                     and (stg is None or p['stage_code'] == stg) and p['nature_code'] not in bans and time_ok(p, t, sd, lang)]
                if not c:
                    return None
                c.sort(key=lambda pi: (used_key(pi), pi))
                return c[0]

            def eval_stage(a):
                cur = stage[a]
                gs = [g for g in goals if g['axis'] == a and g['pool'] == 'AXIS_STAGE' and g['date'] < sd and (sd - g['date']).days <= 56
                      and (stage_chg[a] is None or g['date'] >= stage_chg[a])]
                gs = gs[-4:]
                st = snap.get(a, ('OBSERVING', 0))[0]
                if len(gs) >= 2 and not gs[-1]['done'] and not gs[-2]['done'] and cur != 'INTRO':
                    stage[a] = STAGES[STAGES.index(cur) - 1]
                    stage_chg[a] = sd
                    return
                cap = {'NEEDS_WORK': 'BASE', 'NORMAL': 'CHALLENGE', 'GOOD': 'CHALLENGE'}.get(st)
                if cap and len(gs) >= 3 and sum(g['done'] for g in gs) >= P['stage_up_completions'] and STAGES.index(cur) < STAGES.index(cap):
                    stage[a] = STAGES[STAGES.index(cur) + 1]
                    stage_chg[a] = sd

            def axis_pick(a):
                eval_stage(a)
                for s in reversed(STAGES[:STAGES.index(stage[a]) + 1]):
                    r = pick('AXIS_STAGE', a, s)
                    if r is not None:
                        return r
                return None

            pi = None
            if fscore <= 0:
                pi = pick('RECOVERY')
            if pi is None and rstate in ('ANSWERED', 'REUSED'):
                pi = axis_pick(rq['axis_key'])
            if pi is None:
                for a in AXORD:
                    if a in L:
                        pi = axis_pick(a)
                        if pi is not None:
                            break
            if pi is None:
                for a in AXORD:
                    pi = axis_pick(a)
                    if pi is not None:
                        break
            if pi is not None:
                p = GP[pi]
                goal = {'pi': pi, 'date': sd, 'axis': p['axis_key'], 'pool': p['pool_type'], 'stage': p['stage_code'], 'done': bool(done)}
                goals.append(goal)
            else:
                goal = {'pi': None}
        out.append(dict(d=i + 1, sd=sd.isoformat(), t=t, meal=ml, md=md.isoformat(), rot=AXN.get(rq['axis_key']) if rq else None,
                        rstate=rstate, freused=freused, snap={AXID[a]: v for a, v in snap.items()}, goal=goal))
    return out

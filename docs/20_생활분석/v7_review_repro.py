"""Read-only probes of the supplied v7 handoff. Run from project root."""
import importlib.util
import json
from pathlib import Path
from copy import deepcopy

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / '지표산식_정훈샘/maireport-external-developer-v7.0-handoff'
spec = importlib.util.spec_from_file_location('calc', BASE / 'sample_v7_calculator.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
out = {}
def hc(steps=None, sleep=None):
    return m.normalize_device_export({'provider':'health_connect','user_timezone':'Asia/Seoul',
        'records':{'steps':steps or [],'sleep_sessions':sleep or []}})
def step(start, end, count=100, id='a'):
    return {'startTime':start,'endTime':end,'count':count,
            'metadata':{'id':id,'dataOrigin':{'packageName':'test.origin'}}}
def stamp(time, day='01'):
    return f'2026-09-{day}T{time}:00+09:00'
days = [{'day':f'2026-09-{n:02d}', 'i3':{'bedtime_minute_local':1380+(n%3)*10,
        'wake_time_minute_local':420+(n%3)*10}} for n in range(1,15)]
out['sleep_routine_only_14_days'] = m.score_i3(days)
out['midnight_clock_standard_deviation'] = m.routine_stability([
    {'bedtime_minute_local':b,'wake_time_minute_local':420} for b in [1430,0,10]])
cross = hc([step(stamp('08:50'),stamp('09:10'))])
out['partition_boundary'] = cross['days'][0]['i1']
out['cross_midnight_steps'] = hc([step(stamp('23:50'),stamp('00:10','02'))])['days'][0]['i1']
overlap = hc([step(stamp('08:00'),stamp('09:00'),100,'a'),
              step(stamp('08:30'),stamp('09:30'),200,'b')])
out['overlap_volume'] = overlap['days'][0]['i3']
sleep = {'startTime':stamp('23:00'), 'endTime':stamp('07:00','02'),
         'metadata':{'id':'sleep','dataOrigin':{'packageName':'test.origin'}},
         'stages':[{'startTime':stamp('23:00'),'endTime':stamp('01:00','02'),'stage':1},
                   {'startTime':stamp('01:00','02'),'endTime':stamp('07:00','02'),'stage':2}]}
out['8h_session_6h_asleep'] = hc(sleep=[sleep])['days'][0]
out['missing_exercise'] = cross['days'][0]['i3']['exercise_minutes']
out['i2_cap'] = m.score_i2({'i2':{'daily_steps':12000,'movement_distribution_credit':1}})
out['duplicate_calendar_days'] = m.score_i3([
    {'day':'2026-09-01','i3':{'volume':100}} for _ in range(3)] + [
    {'day':'2026-09-08','i3':{'volume':200}} for _ in range(3)])
out['i1_sleep_only'] = m.score_i1({'i1':{'mode':'rich','sleep_shortfall_minutes':0}})
out['duration_granularity'] = {
    str(minutes):hc([step(stamp('08:00'),stamp(end),100)])['days'][0]['i1']['movement_minutes']
    for minutes,end in [(1,'08:01'),(60,'09:00')]}
out['i1_240_vs_480'] = [m.score_i1({'i1':{'movement_minutes':v,
    'active_partition_count':4,'partition_count':8,'activity_concentration':0.25,
    'sleep_shortfall_minutes':0}})['display_score_0_100'] for v in [240,480]]
schema = json.loads((BASE/'contracts/indicator-v7-output.schema.json').read_text(encoding='utf-8'))
out['output_contract_type_mismatch'] = {
    'schema_available_components_type':schema['$defs']['coverage']['properties']['available_components']['type'],
    'actual_i1_insufficient_coverage':m.score_i1({'i1':{}})['coverage'],
    'schema_components_type':schema['$defs']['coverage']['properties']['components']['type'],
    'actual_i3_no_components_coverage':out['sleep_routine_only_14_days']['coverage']}
try:
    from jsonschema import Draft202012Validator
    schema = json.loads((BASE/'contracts/indicator-v7-output.schema.json').read_text(encoding='utf-8'))
    sample = json.loads((BASE/'examples/v7-normalized-input.example.json').read_text(encoding='utf-8'))
    sample['days'] = [deepcopy(sample['days'][0])]
    for field in sample['days'][0]['i1']:
        if field != 'mode': sample['days'][0]['i1'][field] = None
    sample['days'][0]['i1']['mode'] = 'rich'
    out['output_schema_errors'] = [f'{list(e.absolute_path)}: {e.message}'
        for e in Draft202012Validator(schema).iter_errors(m.calculate(sample))]
except ImportError:
    out['output_schema_errors'] = 'jsonschema unavailable'
text = json.dumps(out,ensure_ascii=False,indent=2)
(ROOT/'outputs/v7_review_repro_results.json').write_text(text+'\n',encoding='utf-8')
print(text)

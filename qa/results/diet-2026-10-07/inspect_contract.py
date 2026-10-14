import json
from pathlib import Path
from collections import Counter
import openpyxl

root = Path(__file__).resolve().parents[3]
book = root / 'outputs/mai-report-policy/식이/maiReport_식이_개발전달_데이터계약_v1.0.0.xlsx'
wb = openpyxl.load_workbook(book, data_only=True)
data = {s.title: [list(r) for r in s.values] for s in wb}
Path(__file__).with_name('contract-extract.json').write_text(json.dumps(data, ensure_ascii=False, default=str, indent=2), encoding='utf-8')
for name in ['목표문구', '노출조건', '질문', '선택지', '내정보질환매핑']:
    rows = data[name]
    header = rows[0]
    records = [dict(zip(header, r)) for r in rows[1:] if r[0] is not None]
    print(name, len(records))
    for field in ['source_status', 'parse_status', 'after_dinner_eligible']:
        if field in header: print(field, dict(Counter(str(r[field]) for r in records)))
    if name in ['목표문구', '노출조건']:
        keys = [(r['phrase_id'], r['phrase_version']) for r in records]
        print('duplicate_keys', len(keys) - len(set(keys)))
for name in ['구현기준', '검증규칙', '설정파라미터']:
    for row in data[name][1:]:
        if row[0] in ['R-03', 'R-09', 'V-39', 'V-42', 'CFG-041', 'CFG-068', 'CFG-069']:
            print(name, row)

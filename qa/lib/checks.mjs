// 계약 엑셀의 데이터 점검. 점검 하나는 { check, sheet, ... } 한 줄로 적는다.
import { sheetRecords } from './xlsx.mjs';

const SAMPLE = 5;
const keyOf = (record, keys) => keys.map(k => String(record[k] ?? '')).join(' + ');
const matchesWhere = (record, where = {}) => Object.entries(where)
  .every(([field, want]) => (Array.isArray(want) ? want.map(String).includes(String(record[field])) : String(record[field]) === String(want)));
const isEmpty = value => value == null || String(value).trim() === '';
const describeRow = (record, fields) => fields.map(f => `${f}=${record[f] ?? '(빈칸)'}`).join(', ');

const CHECKS = {
  // 행 수 (where 조건을 주면 그 조건에 맞는 행 수)
  count({ rows, spec }) {
    const actual = rows.filter(r => matchesWhere(r, spec.where)).length;
    return { pass: actual === spec.expected, actual, expected: spec.expected };
  },
  // 키 조합이 겹치지 않는다
  unique({ rows, spec }) {
    const seen = new Map();
    rows.forEach(r => { const k = keyOf(r, spec.keys); seen.set(k, (seen.get(k) ?? 0) + 1); });
    const dup = [...seen].filter(([, n]) => n > 1).map(([k, n]) => `${k} (${n}번)`);
    return { pass: dup.length === 0, actual: `중복 ${dup.length}건`, expected: '중복 0건', samples: dup.slice(0, SAMPLE) };
  },
  // 필드 값이 허용 목록 안에 있다
  allIn({ rows, spec }) {
    const allowed = spec.values.map(String);
    const bad = rows.filter(r => !allowed.includes(String(r[spec.field])));
    return { pass: bad.length === 0, actual: `허용 밖 ${bad.length}행 / 전체 ${rows.length}행`, expected: `${spec.field} ∈ {${allowed.join(', ')}}`, samples: bad.slice(0, SAMPLE).map(r => describeRow(r, [Object.keys(r)[0], spec.field])) };
  },
  // 숫자 범위 (min·max 중 하나만 줘도 된다)
  range({ rows, spec }) {
    const bad = rows.filter(r => {
      const value = Number(r[spec.field]);
      if (isEmpty(r[spec.field]) || Number.isNaN(value)) return true;
      return (spec.min != null && value < spec.min) || (spec.max != null && value > spec.max);
    });
    return { pass: bad.length === 0, actual: `범위 밖·숫자 아님 ${bad.length}행`, expected: `${spec.min ?? '-∞'} ≤ ${spec.field} ≤ ${spec.max ?? '∞'}`, samples: bad.slice(0, SAMPLE).map(r => describeRow(r, [Object.keys(r)[0], spec.field])) };
  },
  // 글자 수 상한
  maxLength({ rows, spec }) {
    const bad = rows.filter(r => !isEmpty(r[spec.field]) && [...String(r[spec.field])].length > spec.max);
    return { pass: bad.length === 0, actual: `초과 ${bad.length}행`, expected: `${spec.field} ${spec.max}자 이하`, samples: bad.slice(0, SAMPLE).map(r => `${r[Object.keys(r)[0]]}: "${r[spec.field]}" (${[...String(r[spec.field])].length}자)`) };
  },
  // 빈칸 금지
  notEmpty({ rows, spec }) {
    const bad = rows.filter(r => isEmpty(r[spec.field]));
    return { pass: bad.length === 0, actual: `빈칸 ${bad.length}행`, expected: `${spec.field} 빈칸 없음`, samples: bad.slice(0, SAMPLE).map(r => String(r[Object.keys(r)[0]])) };
  },
  // by 값마다 행 수가 expected
  groupCount({ rows, spec }) {
    const groups = new Map();
    rows.forEach(r => { const k = keyOf(r, [].concat(spec.by)); groups.set(k, (groups.get(k) ?? 0) + 1); });
    const bad = [...groups].filter(([, n]) => n !== spec.expected).map(([k, n]) => `${k}: ${n}개`);
    return { pass: bad.length === 0, actual: `묶음 ${groups.size}개 중 어긋남 ${bad.length}개`, expected: `묶음마다 ${spec.expected}개`, samples: bad.slice(0, SAMPLE) };
  },
  // 두 시트의 키 집합이 같다
  sameKeys({ book, spec }) {
    const [a, b] = spec.sheets.map(s => new Set(sheetRecords(book, s).records.map(r => keyOf(r, spec.keys))));
    const onlyA = [...a].filter(k => !b.has(k)); const onlyB = [...b].filter(k => !a.has(k));
    return { pass: !onlyA.length && !onlyB.length, actual: `${spec.sheets[0]}에만 ${onlyA.length}개, ${spec.sheets[1]}에만 ${onlyB.length}개`, expected: '양쪽 키 집합 일치', samples: [...onlyA.map(k => `${spec.sheets[0]}에만: ${k}`), ...onlyB.map(k => `${spec.sheets[1]}에만: ${k}`)].slice(0, SAMPLE) };
  },
  // 참조 값이 다른 시트에 존재한다
  foreignKey({ book, rows, spec }) {
    const ref = new Set(sheetRecords(book, spec.refSheet).records.map(r => String(r[spec.refField])));
    const bad = rows.filter(r => !isEmpty(r[spec.field]) && !ref.has(String(r[spec.field])));
    return { pass: bad.length === 0, actual: `없는 참조 ${bad.length}행`, expected: `${spec.field} → ${spec.refSheet}.${spec.refField}에 존재`, samples: bad.slice(0, SAMPLE).map(r => describeRow(r, [Object.keys(r)[0], spec.field])) };
  },
};

export const CHECK_TYPES = Object.keys(CHECKS);

export function runDataCheck(book, spec) {
  const fn = CHECKS[spec.check];
  if (!fn) return { status: 'ERROR', actual: `모르는 점검 종류: ${spec.check} (가능: ${CHECK_TYPES.join(', ')})` };
  try {
    const rows = spec.sheet ? sheetRecords(book, spec.sheet).records.filter(r => matchesWhere(r, spec.check === 'count' ? {} : spec.where)) : [];
    const result = fn({ book, rows, spec });
    return { status: result.pass ? 'PASS' : 'FAIL', actual: result.actual, expected: result.expected, samples: result.samples ?? [] };
  } catch (error) {
    return { status: 'ERROR', actual: error.message };
  }
}

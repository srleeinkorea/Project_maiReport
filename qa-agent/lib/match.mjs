// 기대값 비교. 기대값에 적은 키만 본다(부분 일치).
// 연산자: $in $ne $gt $gte $lt $lte $exists $contains $length
const isPlain = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const isOperator = value => isPlain(value) && Object.keys(value).length > 0 && Object.keys(value).every(k => k.startsWith('$'));

export function deepEqual(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function getPath(value, path) {
  if (!path) return value;
  return String(path).split('.').reduce((acc, key) => (acc == null ? undefined : acc[key]), value);
}

function checkOperator(actual, ops, path, out) {
  for (const [op, want] of Object.entries(ops)) {
    let ok;
    if (op === '$in') ok = want.some(w => deepEqual(w, actual));
    else if (op === '$ne') ok = !deepEqual(want, actual);
    else if (op === '$gt') ok = actual > want;
    else if (op === '$gte') ok = actual >= want;
    else if (op === '$lt') ok = actual < want;
    else if (op === '$lte') ok = actual <= want;
    else if (op === '$exists') ok = (actual !== undefined) === want;
    else if (op === '$contains') ok = (typeof actual === 'string' || Array.isArray(actual)) && actual.includes(want);
    else if (op === '$length') ok = actual != null && actual.length === want;
    else throw new Error(`모르는 비교 연산자: ${op}`);
    if (!ok) out.push({ path, expected: { [op]: want }, actual });
  }
}

/** 어긋난 곳 목록을 돌려준다. 빈 배열이면 일치. */
export function compare(actual, expected, path = '', out = []) {
  if (isOperator(expected)) checkOperator(actual, expected, path || '(결과)', out);
  else if (Array.isArray(expected)) {
    if (!Array.isArray(actual) || actual.length !== expected.length) out.push({ path: path || '(결과)', expected, actual });
    else expected.forEach((item, i) => compare(actual[i], item, `${path}[${i}]`, out));
  } else if (isPlain(expected)) {
    if (!isPlain(actual)) out.push({ path: path || '(결과)', expected, actual });
    else for (const [key, value] of Object.entries(expected)) compare(actual[key], value, path ? `${path}.${key}` : key, out);
  } else if (!Object.is(actual, expected)) out.push({ path: path || '(결과)', expected, actual });
  return out;
}

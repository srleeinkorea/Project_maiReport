// QA 계획(qa-plan.json) 하나를 실행해 결과 객체를 만든다.
// 순서: 기존 테스트 → 데이터 점검 → 시나리오 케이스 → 정적 발견 정리 → 규칙 추적 → 판정
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { readWorkbook, sheetRecords } from './xlsx.mjs';
import { runDataCheck } from './checks.mjs';
import { compare, deepEqual, getPath } from './match.mjs';

export const SEVERITIES = ['높음', '보통', '낮음'];

export function findRepoRoot(start) {
  let dir = path.resolve(start);
  while (true) {
    if (fs.existsSync(path.join(dir, '.git')) || fs.existsSync(path.join(dir, 'qa-agent', 'bin'))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) return process.cwd();
    dir = parent;
  }
}

export function todayInSeoul() {
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul' }).format(new Date());
}

const clone = value => (value === undefined ? undefined : JSON.parse(JSON.stringify(value)));
const isPlain = value => value !== null && typeof value === 'object' && !Array.isArray(value);

/** {"$fixture": "이름", ...덮어쓸 키} 를 fixtures 값으로 바꾼다. 중첩도 처리한다. */
export function resolveFixtures(value, fixtures, trail = []) {
  if (Array.isArray(value)) return value.map(v => resolveFixtures(v, fixtures, trail));
  if (!isPlain(value)) return value;
  if ('$fixture' in value) {
    const name = value.$fixture;
    if (!(name in fixtures)) throw new Error(`fixtures에 "${name}"이 없습니다`);
    if (trail.includes(name)) throw new Error(`fixture가 서로를 참조합니다: ${[...trail, name].join(' → ')}`);
    const base = resolveFixtures(clone(fixtures[name]), fixtures, [...trail, name]);
    const { $fixture, ...rest } = value;
    const overrides = resolveFixtures(rest, fixtures, trail);
    return isPlain(base) ? { ...base, ...overrides } : base;
  }
  return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, resolveFixtures(v, fixtures, trail)]));
}

const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').slice(0, 12);
const rel = (root, file) => path.relative(root, file).split(path.sep).join('/');

function runExistingTests(root, targetDir, files) {
  if (!files?.length) return { ran: false, tests: 0, pass: 0, fail: 0, failures: [], command: null };
  const absolute = files.map(f => path.resolve(targetDir, f));
  const missing = absolute.filter(f => !fs.existsSync(f));
  if (missing.length) return { ran: false, tests: 0, pass: 0, fail: 0, failures: missing.map(f => `파일 없음: ${rel(root, f)}`), command: null, error: true };
  const args = ['--test', '--test-reporter=tap', ...absolute];
  const run = spawnSync(process.execPath, args, { cwd: root, encoding: 'utf8', timeout: 300_000, maxBuffer: 64 * 1024 * 1024 });
  const out = `${run.stdout ?? ''}\n${run.stderr ?? ''}`;
  const num = key => Number(out.match(new RegExp(`^# ${key} (\\d+)`, 'm'))?.[1] ?? 0);
  const failures = [...out.matchAll(/^\s*not ok \d+ - (.+)$/gm)].map(m => m[1].trim()).filter(t => !t.endsWith('.mjs'));
  return {
    ran: true, tests: num('tests'), pass: num('pass'), fail: num('fail'), skipped: num('skipped'),
    failures, exitCode: run.status, error: run.status !== 0 && num('fail') === 0,
    command: `node --test ${files.map(f => `"${rel(root, path.resolve(targetDir, f))}"`).join(' ')}`,
  };
}

const moduleCache = new Map();
async function loadExport(targetDir, modulePath, exportName) {
  const file = path.resolve(targetDir, modulePath);
  if (!moduleCache.has(file)) moduleCache.set(file, import(pathToFileURL(file).href));
  const mod = await moduleCache.get(file);
  if (typeof mod[exportName] !== 'function') throw new Error(`${modulePath}에 함수 ${exportName}가 없습니다 (내보낸 이름: ${Object.keys(mod).join(', ')})`);
  return mod[exportName];
}

async function invoke(fn, args) {
  try {
    const value = await (Array.isArray(args) ? fn(...clone(args)) : fn(clone(args)));
    return { ok: true, value: clone(value) };
  } catch (error) {
    return { ok: false, error: { name: error?.name, message: error?.message ?? String(error) } };
  }
}

async function runCase(spec, targetDir, fixtures) {
  const base = { id: spec.id, title: spec.title, scenario: spec.scenario, rules: spec.rules ?? [], severity: spec.severity ?? '보통', basis: spec.basis, note: spec.note, where: spec.where, suggestion: spec.suggestion, type: spec.type ?? 'call' };
  try {
    const fn = await loadExport(targetDir, spec.module, spec.export);
    if (base.type === 'same') {
      const [a, b] = spec.calls.map(c => resolveFixtures(c.args, fixtures));
      const [ra, rb] = [await invoke(fn, a), await invoke(fn, b)];
      if (!ra.ok || !rb.ok) return { ...base, status: 'ERROR', actual: (ra.error ?? rb.error).message };
      const [va, vb] = [getPath(ra.value, spec.compare), getPath(rb.value, spec.compare)];
      return {
        ...base, status: deepEqual(va, vb) ? 'PASS' : 'FAIL',
        input: Object.fromEntries(spec.calls.map((c, i) => [c.label ?? `입력${i + 1}`, [a, b][i]])),
        expected: `두 입력의 ${spec.compare ?? '결과'}가 같다`,
        actual: Object.fromEntries(spec.calls.map((c, i) => [c.label ?? `입력${i + 1}`, [va, vb][i]])),
      };
    }
    const args = resolveFixtures(spec.args, fixtures);
    const result = await invoke(fn, args);
    if (spec.expectError) {
      const want = spec.expectError === true ? null : String(spec.expectError);
      const pass = !result.ok && (!want || result.error.message.includes(want));
      return { ...base, status: pass ? 'PASS' : 'FAIL', input: args, expected: `오류${want ? `(${want})` : ''}`, actual: result.ok ? result.value : result.error.message };
    }
    if (!result.ok) return { ...base, status: 'ERROR', input: args, expected: spec.expect, actual: `${result.error.name}: ${result.error.message}` };
    const diffs = compare(result.value, spec.expect);
    return { ...base, status: diffs.length ? 'FAIL' : 'PASS', input: args, expected: spec.expect, actual: result.value, diffs };
  } catch (error) {
    return { ...base, status: 'ERROR', actual: error.message };
  }
}

function loadRules(book, ruleSheets = []) {
  const rules = [];
  for (const sheet of ruleSheets) {
    for (const record of sheetRecords(book, sheet.sheet).records) {
      const id = record[sheet.idField];
      if (id) rules.push({ id: String(id), sheet: sheet.sheet, text: String(record[sheet.textField] ?? '') });
    }
  }
  return rules;
}

function verdictOf({ tests, cases, dataChecks, findings }) {
  const failed = [...cases, ...dataChecks, ...findings].filter(item => item.status === 'FAIL');
  const errors = [...cases, ...dataChecks].filter(item => item.status === 'ERROR');
  const blockers = failed.filter(item => item.severity === '높음');
  if (tests.fail > 0 || tests.error) return { level: '보류', reason: `기존 테스트 실패 ${tests.fail}건${tests.error ? ' (테스트 실행 오류)' : ''}` };
  if (blockers.length) return { level: '보류', reason: `심각도 높음 ${blockers.length}건 (${blockers.map(b => b.id).join(', ')})` };
  if (errors.length) return { level: '보류', reason: `실행 오류 ${errors.length}건 — 케이스나 대상 코드를 먼저 확인해야 판정 가능` };
  if (failed.length) return { level: '조건부 통과', reason: `보통·낮음 ${failed.length}건을 고치는 조건` };
  return { level: '통과', reason: '계획한 항목이 모두 기준과 일치' };
}

export async function runPlan(planFile, { date } = {}) {
  const planPath = path.resolve(planFile);
  const plan = JSON.parse(fs.readFileSync(planPath, 'utf8').replace(/^﻿/, ''));
  const root = findRepoRoot(path.dirname(planPath));
  const targetDir = path.resolve(root, plan.target);
  if (!fs.existsSync(targetDir)) throw new Error(`target 폴더가 없습니다: ${plan.target}`);
  const fixtures = plan.fixtures ?? {};

  const contractFile = plan.baseline?.contract ? path.resolve(targetDir, plan.baseline.contract) : null;
  const book = contractFile ? readWorkbook(contractFile) : null;

  const tests = runExistingTests(root, targetDir, plan.existingTests);
  const dataChecks = (plan.dataChecks ?? []).map(spec => ({
    id: spec.id, title: spec.title, kind: spec.kind ?? '데이터', rules: spec.rules ?? [], severity: spec.severity ?? '보통', basis: spec.basis, sheet: spec.sheet, check: spec.check,
    ...(book ? runDataCheck(book, spec) : { status: 'ERROR', actual: 'baseline.contract가 없어 데이터 점검을 할 수 없습니다' }),
  }));
  const cases = [];
  for (const spec of plan.cases ?? []) cases.push(await runCase(spec, targetDir, fixtures));
  const findings = (plan.findings ?? []).map(f => ({ ...f, rules: f.rules ?? [], severity: f.severity ?? '보통', status: f.status ?? 'FAIL' }));

  const rules = book ? loadRules(book, plan.baseline.ruleSheets) : [];
  const covered = new Map();
  for (const item of [...cases, ...dataChecks, ...findings]) {
    for (const ruleId of item.rules) {
      if (!covered.has(ruleId)) covered.set(ruleId, []);
      covered.get(ruleId).push({ id: item.id, status: item.status });
    }
  }
  const trace = rules.map(rule => ({ ...rule, items: covered.get(rule.id) ?? [] }));
  const knownIds = new Set(rules.map(r => r.id));
  const unknownRuleRefs = [...covered.keys()].filter(id => rules.length && !knownIds.has(id) && !/^CFG-/.test(id));

  const result = {
    feature: plan.feature,
    date: date ?? todayInSeoul(),
    plan: rel(root, planPath),
    target: plan.target,
    baseline: {
      contract: contractFile ? { file: rel(root, contractFile), sha256: sha(contractFile), status: book?.['안내'] ? String(sheetRecords(book, '안내').records.find(r => String(Object.values(r)[0]).includes('발행'))?.['내용'] ?? '') : '' } : null,
      documents: (plan.baseline?.documents ?? []).map(d => rel(root, path.resolve(targetDir, d))),
    },
    scope: plan.scope ?? { in: [], out: [] },
    environment: { node: process.version, platform: process.platform },
    tests, dataChecks, cases, findings, trace, unknownRuleRefs,
    openQuestions: plan.openQuestions ?? [],
  };
  result.summary = {
    cases: tally(cases), dataChecks: tally(dataChecks), findings: tally(findings),
    rules: { total: trace.length, covered: trace.filter(t => t.items.length).length },
  };
  result.verdict = verdictOf(result);
  return { result, root };
}

function tally(items) {
  const out = { total: items.length, PASS: 0, FAIL: 0, ERROR: 0, '확인 필요': 0 };
  items.forEach(item => { out[item.status] = (out[item.status] ?? 0) + 1; });
  return out;
}

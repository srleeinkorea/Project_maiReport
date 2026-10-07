#!/usr/bin/env node
// QA 에이전트 실행기. 사용법은 `node qa-agent/bin/qa.mjs help`.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';
import { readWorkbook, sheetRecords } from '../lib/xlsx.mjs';
import { runPlan, findRepoRoot } from '../lib/runner.mjs';
import { renderHtml, renderMarkdown } from '../lib/report.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const AGENT_DIR = path.resolve(HERE, '..');
const ROOT = findRepoRoot(AGENT_DIR);

const HELP = `QA 에이전트 실행기

  init <기능이름> --target <대상 폴더>
      대상 폴더를 훑어 테스트·계약 엑셀·문서·내보낸 함수를 찾고
      qa-agent/plans/<기능이름>.qa-plan.json 뼈대를 만든다 (이미 있으면 덮어쓰지 않음).

  extract <엑셀 파일> [--sheet 시트1,시트2] [--out 파일.json]
      시트 목록·행 수·머리글을 보여 준다. --sheet를 주면 그 시트의 행을 한 줄씩 출력한다.

  run <계획 파일> [--out 폴더] [--date YYYY-MM-DD]
      계획을 실행하고 outputs/qa/<기능>-<날짜>/ 에 보고서(HTML)·요약(MD)·결과(JSON)를 쓴다.
      종료 코드: 0 = 통과 또는 조건부 통과, 1 = 보류, 2 = 실행기 사용 오류.
`;

function parseArgs(argv) {
  const positional = []; const flags = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--')) flags[argv[i].slice(2)] = argv[i + 1]?.startsWith('--') || argv[i + 1] === undefined ? true : argv[++i];
    else positional.push(argv[i]);
  }
  return { positional, flags };
}

const relRoot = file => path.relative(ROOT, file).split(path.sep).join('/');

async function cmdInit([feature], { target }) {
  if (!feature || !target) throw new UsageError('init <기능이름> --target <대상 폴더> 형식으로 적어 주세요');
  const targetDir = path.resolve(ROOT, target);
  if (!fs.existsSync(targetDir)) throw new UsageError(`대상 폴더가 없습니다: ${target}`);
  const files = fs.readdirSync(targetDir);
  const tests = files.filter(f => /\.test\.m?js$/.test(f));
  const workbooks = files.filter(f => /\.xlsx$/i.test(f) && !f.startsWith('~$'));
  const docs = files.filter(f => /\.(md|html)$/i.test(f));
  const modules = files.filter(f => /\.mjs$/.test(f) && !/\.test\.mjs$/.test(f));

  const ruleSheetGuess = [];
  let contract = workbooks.find(f => /계약|contract/i.test(f)) ?? workbooks[0] ?? null;
  if (contract) {
    const book = readWorkbook(path.join(targetDir, contract));
    for (const name of Object.keys(book)) {
      const { header } = sheetRecords(book, name);
      const idField = header.find(h => h && /(규칙|기준)\s*ID/i.test(h));
      if (idField) ruleSheetGuess.push({ sheet: name, idField, textField: header.find(h => h && /(검사|확정 규칙|내용|규칙$)/.test(h) && h !== idField) ?? header[1] });
    }
  }

  console.log(`\n# ${feature} — 대상 폴더 훑기 (${relRoot(targetDir)})\n`);
  console.log(`기존 테스트 ${tests.length}개: ${tests.join(', ') || '없음'}`);
  console.log(`엑셀 ${workbooks.length}개: ${workbooks.join(', ') || '없음'}  → 기준(계약)으로 고른 파일: ${contract ?? '없음'}`);
  console.log(`규칙 시트 추정: ${ruleSheetGuess.map(r => `${r.sheet}(${r.idField})`).join(', ') || '없음'}`);
  console.log(`문서 ${docs.length}개`);
  console.log('\n내보낸 함수 (케이스의 module / export 후보):');
  for (const m of modules) {
    try {
      const mod = await import(pathToFileURL(path.join(targetDir, m)).href);
      const fns = Object.entries(mod).filter(([, v]) => typeof v === 'function').map(([k]) => k);
      console.log(`  ${m}: ${fns.join(', ') || '(함수 없음)'}`);
    } catch (error) {
      console.log(`  ${m}: 불러오기 실패 — ${error.message}`);
    }
  }

  const planFile = path.join(AGENT_DIR, 'plans', `${feature}.qa-plan.json`);
  if (fs.existsSync(planFile)) {
    console.log(`\n계획 파일이 이미 있어 그대로 둡니다: ${relRoot(planFile)}`);
    return 0;
  }
  const template = JSON.parse(fs.readFileSync(path.join(AGENT_DIR, 'templates', 'qa-plan.template.json'), 'utf8'));
  const plan = {
    ...template,
    feature,
    target: relRoot(targetDir),
    baseline: { contract, documents: docs.filter(d => /점검|결정|정의|기획/.test(d)).slice(0, 5), ruleSheets: ruleSheetGuess },
    existingTests: tests,
  };
  fs.mkdirSync(path.dirname(planFile), { recursive: true });
  fs.writeFileSync(planFile, `${JSON.stringify(plan, null, 2)}\n`, 'utf8');
  console.log(`\n계획 뼈대를 만들었습니다: ${relRoot(planFile)}`);
  console.log('다음 단계: 기준 문서의 규칙을 읽고 cases · dataChecks · findings를 채운 뒤 run 하세요.');
  return 0;
}

function cmdExtract([file], { sheet, out }) {
  if (!file) throw new UsageError('extract <엑셀 파일> 형식으로 적어 주세요');
  const book = readWorkbook(path.resolve(file));
  if (out) {
    const all = Object.fromEntries(Object.keys(book).map(name => [name, sheetRecords(book, name).records]));
    fs.writeFileSync(path.resolve(out), JSON.stringify(all, null, 2), 'utf8');
    console.log(`전체 시트를 썼습니다: ${out}`);
  }
  if (sheet) {
    for (const name of String(sheet).split(',')) {
      const { header, records } = sheetRecords(book, name.trim());
      console.log(`\n## ${name} (${records.length}행) 머리글: ${header.filter(Boolean).join(' | ')}`);
      records.forEach(r => console.log(JSON.stringify(r)));
    }
    return 0;
  }
  for (const name of Object.keys(book)) {
    const { header, records } = sheetRecords(book, name);
    console.log(`${name.padEnd(12)} ${String(records.length).padStart(4)}행  ${header.filter(Boolean).join(' | ')}`);
  }
  return 0;
}

async function cmdRun([planFile], { out, date }) {
  if (!planFile) throw new UsageError('run <계획 파일> 형식으로 적어 주세요');
  const { result } = await runPlan(planFile, { date: date === true ? undefined : date });
  const outDir = path.resolve(ROOT, out && out !== true ? out : path.join('outputs', 'qa', `${result.feature}-${result.date}`));
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'results.json'), `${JSON.stringify(result, null, 2)}\n`, 'utf8');
  fs.writeFileSync(path.join(outDir, `${result.feature}_QA보고서.html`), renderHtml(result), 'utf8');
  const md = renderMarkdown(result);
  fs.writeFileSync(path.join(outDir, `${result.feature}_QA요약.md`), md, 'utf8');
  fs.copyFileSync(path.resolve(planFile), path.join(outDir, 'qa-plan.snapshot.json'));
  console.log(md);
  console.log(`보고서: ${relRoot(path.join(outDir, `${result.feature}_QA보고서.html`))}`);
  return result.verdict.level === '보류' ? 1 : 0;
}

class UsageError extends Error {}

const [command, ...rest] = process.argv.slice(2);
const { positional, flags } = parseArgs(rest);
const commands = { init: cmdInit, extract: cmdExtract, run: cmdRun };
try {
  if (!commands[command]) { console.log(HELP); process.exitCode = command && command !== 'help' ? 2 : 0; }
  else process.exitCode = await commands[command](positional, flags);
} catch (error) {
  console.error(`\n오류: ${error.message}`);
  if (!(error instanceof UsageError)) console.error(error.stack);
  process.exitCode = 2;
}

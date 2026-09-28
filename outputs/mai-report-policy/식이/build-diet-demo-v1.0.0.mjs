import fs from 'node:fs/promises';
import { DIET_REFERENCE } from './diet-reference-config-v1.0.0.mjs';

const directory = new URL('.', import.meta.url);
const jsonPath = new URL('diet-reference-v1.0.0.json', directory);
const htmlPath = new URL('mai-report-식이_시연데모_v1.0.0.html', directory);
const reference = DIET_REFERENCE;
if (reference.version !== '1.0.0') throw new Error('데모 참조 데이터 버전은 1.0.0이어야 합니다');
await fs.writeFile(jsonPath, `${JSON.stringify(reference, null, 2)}\n`, 'utf8');
let html = await fs.readFile(htmlPath, 'utf8');
const start = '<!-- DIET_REFERENCE_START -->';
const end = '<!-- DIET_REFERENCE_END -->';
const block = `${start}\n<script id="diet-reference-data" type="application/json">${JSON.stringify(reference)}</script>\n${end}`;
if (!html.includes(start) || !html.includes(end)) throw new Error('데모 참조 데이터 삽입 위치가 없습니다');
html = html.replace(new RegExp(`${start}[\\s\\S]*?${end}`), block);
await fs.writeFile(htmlPath, html, 'utf8');
console.log(`synced ${htmlPath.pathname}`);

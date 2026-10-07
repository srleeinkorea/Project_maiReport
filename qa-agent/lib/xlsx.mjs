// 의존성 없이 .xlsx를 읽는다. 엑셀 파일은 zip 안의 XML 묶음이라
// zip 목차를 직접 읽고 zlib로 풀어 시트별 행 배열로 바꾼다.
// 수식은 마지막으로 저장된 값을 읽고, 날짜는 엑셀 일련번호(숫자) 그대로 둔다.
import fs from 'node:fs';
import zlib from 'node:zlib';

function unzip(buffer) {
  let eocd = -1;
  for (let i = buffer.length - 22; i >= Math.max(0, buffer.length - 65557); i--) {
    if (buffer.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error('xlsx(zip) 형식이 아닙니다');
  const count = buffer.readUInt16LE(eocd + 10);
  let offset = buffer.readUInt32LE(eocd + 16);
  const entries = new Map();
  for (let n = 0; n < count; n++) {
    if (buffer.readUInt32LE(offset) !== 0x02014b50) throw new Error('zip 목차가 손상되었습니다');
    const method = buffer.readUInt16LE(offset + 10);
    const size = buffer.readUInt32LE(offset + 20);
    const nameLength = buffer.readUInt16LE(offset + 28);
    const extraLength = buffer.readUInt16LE(offset + 30);
    const commentLength = buffer.readUInt16LE(offset + 32);
    const local = buffer.readUInt32LE(offset + 42);
    const name = buffer.toString('utf8', offset + 46, offset + 46 + nameLength);
    entries.set(name, { method, size, local });
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return name => {
    const entry = entries.get(name);
    if (!entry) return null;
    const start = entry.local + 30 + buffer.readUInt16LE(entry.local + 26) + buffer.readUInt16LE(entry.local + 28);
    const data = buffer.subarray(start, start + entry.size);
    if (entry.method === 0) return data.toString('utf8');
    if (entry.method === 8) return zlib.inflateRawSync(data).toString('utf8');
    throw new Error(`지원하지 않는 압축 방식(${entry.method}): ${name}`);
  };
}

const decode = text => text
  .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
  .replace(/&#(\d+);/g, (_, dec) => String.fromCodePoint(Number(dec)))
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, '&');

const attr = (source, name) => source.match(new RegExp(`\\b${name}="([^"]*)"`))?.[1];
const textOf = xml => [...xml.replace(/<rPh\b[\s\S]*?<\/rPh>/g, '').matchAll(/<t\b[^>]*>([\s\S]*?)<\/t>/g)].map(m => decode(m[1])).join('');

const columnIndex = ref => {
  let index = 0;
  for (const ch of ref.replace(/\d+$/, '')) index = index * 26 + (ch.charCodeAt(0) - 64);
  return index - 1;
};

function parseSheet(xml, shared) {
  const rows = [];
  for (const rowMatch of xml.matchAll(/<row\b([^>]*?)(?:\/>|>([\s\S]*?)<\/row>)/g)) {
    const rowNumber = Number(attr(rowMatch[1], 'r') ?? rows.length + 1);
    const row = [];
    for (const cell of (rowMatch[2] ?? '').matchAll(/<c\b([^>]*?)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
      const ref = attr(cell[1], 'r');
      const type = attr(cell[1], 't');
      const body = cell[2] ?? '';
      const raw = body.match(/<v>([\s\S]*?)<\/v>/)?.[1];
      let value = null;
      if (type === 's') value = raw == null ? null : shared[Number(raw)];
      else if (type === 'inlineStr') value = textOf(body);
      else if (type === 'str' || type === 'e') value = raw == null ? null : decode(raw);
      else if (type === 'b') value = raw === '1';
      else if (raw != null) value = Number(raw);
      if (value === '') value = null;
      row[ref ? columnIndex(ref) : row.length] = value;
    }
    rows[rowNumber - 1] = Array.from(row, v => v ?? null);
  }
  return Array.from(rows, r => r ?? []);
}

/** 엑셀 파일을 { 시트이름: 행[][] } 로 읽는다. 행·열은 0부터 센다. */
export function readWorkbook(file) {
  const read = unzip(fs.readFileSync(file));
  const sharedXml = read('xl/sharedStrings.xml');
  const shared = sharedXml ? [...sharedXml.matchAll(/<si\b[^>]*>([\s\S]*?)<\/si>/g)].map(m => textOf(m[1])) : [];
  const rels = new Map([...read('xl/_rels/workbook.xml.rels').matchAll(/<Relationship\b([^>]*)\/?>/g)]
    .map(m => [attr(m[1], 'Id'), attr(m[1], 'Target')]));
  const book = {};
  for (const sheet of read('xl/workbook.xml').matchAll(/<sheet\b([^>]*)\/?>/g)) {
    const name = decode(attr(sheet[1], 'name'));
    const target = rels.get(attr(sheet[1], 'r:id'));
    const path = target.startsWith('/') ? target.slice(1) : `xl/${target}`;
    book[name] = parseSheet(read(path) ?? '', shared);
  }
  return book;
}

/**
 * 시트를 { 머리글: 값 } 레코드 목록으로 바꾼다.
 * headerRow를 주지 않으면 비어 있지 않은 칸이 가장 많은 위쪽 10행 중 첫 행을 머리글로 본다.
 * 첫 칸이 빈 행(설명·빈 줄)은 레코드에서 뺀다.
 */
export function sheetRecords(book, sheetName, { headerRow } = {}) {
  const rows = book[sheetName];
  if (!rows) throw new Error(`시트가 없습니다: ${sheetName} (있는 시트: ${Object.keys(book).join(', ')})`);
  let headerIndex = headerRow != null ? headerRow - 1 : 0;
  if (headerRow == null) {
    let best = -1;
    rows.slice(0, 10).forEach((row, index) => {
      const filled = row.filter(v => v != null).length;
      if (filled > best) { best = filled; headerIndex = index; }
    });
  }
  const header = (rows[headerIndex] ?? []).map(v => (v == null ? null : String(v).trim()));
  const records = rows.slice(headerIndex + 1)
    .filter(row => row.some(v => v != null) && row[0] != null)
    .map(row => Object.fromEntries(header.map((h, i) => [h ?? `열${i + 1}`, row[i] ?? null])));
  return { header, headerRow: headerIndex + 1, records };
}

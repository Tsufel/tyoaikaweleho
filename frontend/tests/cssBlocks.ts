// Tiny CSS helpers for token tests (no CSS parser dependency).

/** Custom properties declared in the first block whose selector matches `re`
 *  (brace-matched, so nested blocks stay inside). */
export function cssBlock(src: string, re: RegExp): Record<string, string> {
  const m = re.exec(src);
  if (!m) throw new Error(`no block for ${re}`);
  const start = src.indexOf('{', m.index) + 1;
  let depth = 1;
  let i = start;
  while (depth && i < src.length) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') depth--;
    i++;
  }
  const vars: Record<string, string> = {};
  for (const v of src.slice(start, i - 1).matchAll(/--([a-z0-9-]+)\s*:\s*([^;]+);/g)) vars[v[1]] = v[2].trim();
  return vars;
}

export const stripComments = (src: string): string => src.replace(/\/\*[\s\S]*?\*\//g, '');

/** Top-level rules as { prelude, body } (comments removed). */
export function topLevelRules(src: string): { prelude: string; body: string }[] {
  const s = stripComments(src);
  const out: { prelude: string; body: string }[] = [];
  let i = 0;
  while (i < s.length) {
    const open = s.indexOf('{', i);
    if (open < 0) break;
    const prelude = s.slice(i, open).trim();
    let depth = 1;
    let j = open + 1;
    while (depth && j < s.length) {
      if (s[j] === '{') depth++;
      else if (s[j] === '}') depth--;
      j++;
    }
    out.push({ prelude, body: s.slice(open + 1, j - 1) });
    i = j;
  }
  return out;
}

/** Split a selector list on top-level commas (not inside parentheses). */
export function splitSelectors(prelude: string): string[] {
  const out: string[] = [];
  let depth = 0;
  let cur = '';
  for (const ch of prelude) {
    if (ch === '(') depth++;
    else if (ch === ')') depth--;
    if (ch === ',' && depth === 0) {
      out.push(cur.trim());
      cur = '';
    } else cur += ch;
  }
  if (cur.trim()) out.push(cur.trim());
  return out;
}

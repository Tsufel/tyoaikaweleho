/** Menu typeahead (WAI-ARIA): printable keys gather into a short buffer and
 *  move to the next item whose label starts with it. */

/** Index of the next label (after `from`, wrapping) that starts with `query`;
 *  -1 when none does. A repeated single letter cycles through matches. */
export function typeaheadIndex(labels: string[], from: number, query: string): number {
  const q = query.toLowerCase();
  if (!q || !labels.length) return -1;
  const same = [...q].every((c) => c === q[0]);
  // 'aaa' cycles through the items starting with 'a'
  const needle = same && q.length > 1 ? q[0] : q;
  // a fresh one-letter search starts after the current item; a longer one includes it
  const offset = needle.length === 1 ? 1 : 0;
  const n = labels.length;
  for (let k = 0; k < n; k++) {
    const i = (((from + offset + k) % n) + n) % n;
    if (labels[i].trim().toLowerCase().startsWith(needle)) return i;
  }
  return -1;
}

/** A key buffer that clears itself after `ms` of quiet. */
export function createTypeahead(ms = 500, now: () => number = Date.now) {
  let buf = '';
  let last = -Infinity;
  return (key: string): string => {
    const t = now();
    if (t - last > ms) buf = '';
    last = t;
    buf += key;
    return buf;
  };
}

/** A key that types a character (no modifier; Space stays an activator). */
export const isPrintableKey = (e: KeyboardEvent): boolean =>
  e.key.length === 1 && e.key !== ' ' && !e.ctrlKey && !e.metaKey && !e.altKey;

/** Arrow keys move focus between the `[data-choice]` buttons inside `node`
 *  (←/→ for button rows, ↑/↓ for stacked option cards). */
export function arrowNav(node: HTMLElement) {
  const onKey = (e: KeyboardEvent) => {
    const prev = e.key === 'ArrowLeft' || e.key === 'ArrowUp';
    const next = e.key === 'ArrowRight' || e.key === 'ArrowDown';
    if (!prev && !next) return;
    const btns = [...node.querySelectorAll<HTMLButtonElement>('button[data-choice]')];
    const i = btns.indexOf(document.activeElement as HTMLButtonElement);
    if (i < 0) return;
    e.preventDefault();
    btns[(i + (next ? 1 : -1) + btns.length) % btns.length].focus();
  };
  node.addEventListener('keydown', onKey);
  return { destroy: () => node.removeEventListener('keydown', onKey) };
}

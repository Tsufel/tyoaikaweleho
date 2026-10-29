// Make the WebView feel like an app: no reload, print, find, zoom, browser
// context menu, or navigation by dropping a file. F5 is left to shortcuts.ts
// (timer toggle), which always prevents the reload.

const isEditable = (t: EventTarget | null) => {
  const el = t as HTMLElement | null;
  return !!el && (el.isContentEditable || !!el.closest?.('input, textarea, [contenteditable="true"]'));
};

const CTRL_BLOCK = ['r', 'p', 'f', 'g', 'h', 'j', 'u', 'o', 'l', 'd', 't', 'w', '+', '-', '=', '0', '_'];

function onKey(e: KeyboardEvent): void {
  const ctrl = e.ctrlKey || e.metaKey;
  const k = e.key.toLowerCase();
  const dev = import.meta.env.DEV;
  const block =
    k === 'f3' ||
    k === 'f7' || // caret browsing
    k === 'browserback' ||
    k === 'browserforward' ||
    k === 'browserrefresh' ||
    (e.key === 'F5' && (ctrl || e.shiftKey)) ||
    (e.altKey && (k === 'arrowleft' || k === 'arrowright')) ||
    (ctrl && !e.shiftKey && CTRL_BLOCK.includes(k)) ||
    (ctrl && e.shiftKey && ['r', 'p', 'o', 'delete', 'n'].includes(k)) ||
    (!dev && ctrl && e.shiftKey && ['i', 'j', 'c'].includes(k)) ||
    (!dev && k === 'f12');
  if (block) e.preventDefault();
}

function onWheel(e: WheelEvent): void {
  if (e.ctrlKey) e.preventDefault();
}

function onContextMenu(e: MouseEvent): void {
  if (!isEditable(e.target)) e.preventDefault();
}

function onDrag(e: DragEvent): void {
  // components that accept drops handle them before this (bubble phase)
  e.preventDefault();
  if (e.dataTransfer && e.type === 'dragover') e.dataTransfer.dropEffect = 'none';
}

function onAuxClick(e: MouseEvent): void {
  if (e.button === 1) e.preventDefault();
}

function onClick(e: MouseEvent): void {
  const a = (e.target as HTMLElement | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
  if (a && !a.getAttribute('href')?.startsWith('#')) e.preventDefault();
}

/** Install once at startup. Returns an uninstaller (tests). */
export function harden(): () => void {
  window.addEventListener('keydown', onKey, true);
  window.addEventListener('wheel', onWheel, { capture: true, passive: false });
  window.addEventListener('contextmenu', onContextMenu, true);
  window.addEventListener('dragover', onDrag);
  window.addEventListener('drop', onDrag);
  window.addEventListener('auxclick', onAuxClick, true);
  window.addEventListener('mousedown', onAuxClick, true);
  window.addEventListener('click', onClick);
  return () => {
    window.removeEventListener('keydown', onKey, true);
    window.removeEventListener('wheel', onWheel, true);
    window.removeEventListener('contextmenu', onContextMenu, true);
    window.removeEventListener('dragover', onDrag);
    window.removeEventListener('drop', onDrag);
    window.removeEventListener('auxclick', onAuxClick, true);
    window.removeEventListener('mousedown', onAuxClick, true);
    window.removeEventListener('click', onClick);
  };
}

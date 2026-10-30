<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  import { scale } from '../motion';
  import { clickOutside, portal } from './actions';
  import { liquidGlass } from '../glass/liquidGlass';

  interface Props {
    /** Element the popover is positioned against. */
    anchor: HTMLElement | null | undefined;
    onclose: () => void;
    placement?: 'bottom-start' | 'bottom-end' | 'top-start' | 'top-end';
    /** Match the anchor's width. */
    matchWidth?: boolean;
    /** aria label of the floating panel. */
    label?: string;
    role?: 'dialog' | 'menu' | 'listbox' | 'none';
    class?: string;
    el?: HTMLDivElement;
    children: Snippet;
  }

  let {
    anchor,
    onclose,
    placement = 'bottom-start',
    matchWidth = false,
    label,
    role = 'dialog',
    class: cls = '',
    el = $bindable(),
    children,
  }: Props = $props();

  let pos = $state({ left: 0, top: 0, width: 0, up: false });

  function place() {
    if (!anchor || !el) return;
    const r = anchor.getBoundingClientRect();
    const h = el.offsetHeight;
    const w = matchWidth ? r.width : el.offsetWidth;
    let up = placement.startsWith('top');
    if (!up && r.bottom + 6 + h > window.innerHeight - 8 && r.top - 6 - h > 8) up = true;
    else if (up && r.top - 6 - h < 8 && r.bottom + 6 + h < window.innerHeight - 8) up = false;
    let left = placement.endsWith('end') ? r.right - w : r.left;
    left = Math.min(Math.max(8, left), window.innerWidth - w - 8);
    pos = { left, top: up ? r.top - 6 - h : r.bottom + 6, width: r.width, up };
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      onclose();
      anchor?.focus();
    }
  }

  onMount(() => {
    place();
    const ro = new ResizeObserver(place);
    if (el) ro.observe(el);
    const onWin = () => place();
    window.addEventListener('resize', onWin);
    window.addEventListener('scroll', onWin, true);
    // Escape pressed while focus stayed on the anchor
    const onAnchorKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        onclose();
      }
    };
    anchor?.addEventListener('keydown', onAnchorKey);
    return () => {
      ro.disconnect();
      window.removeEventListener('resize', onWin);
      window.removeEventListener('scroll', onWin, true);
      anchor?.removeEventListener('keydown', onAnchorKey);
    };
  });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  bind:this={el}
  class="popover glass glass-strong lg-overlay {cls}"
  class:up={pos.up}
  data-popover
  role={role === 'none' ? undefined : role}
  aria-label={label}
  style:left="{pos.left}px"
  style:top="{pos.top}px"
  style:width={matchWidth ? `${pos.width}px` : undefined}
  use:portal
  use:clickOutside={{ fn: onclose, ignore: [anchor] }}
  use:liquidGlass={'popover'}
  onkeydown={onKeydown}
  transition:scale={{ start: 0.96, duration: 160 }}
>
  {@render children()}
</div>

<style>
  .popover {
    position: fixed;
    z-index: 150;
    border-radius: var(--radius-md);
    box-shadow: inset 0 1px 0 var(--glass-highlight), var(--shadow-lg);
    transform-origin: top left;
    overflow: hidden;
  }
  .up {
    transform-origin: bottom left;
  }
</style>

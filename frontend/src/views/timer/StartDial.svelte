<script lang="ts">
  import { hhmm } from '../../lib/time';
  import {
    DIAL_MAX_MIN,
    RING,
    agoText,
    dialDay,
    nudgeStart,
    pointerFraction,
    ringPoint,
    startFromLaps,
    unwrapLaps,
  } from './timerLogic';

  /** Idle ring as a dial: drag the knob clockwise (or use arrows / wheel) to
   *  back-date the start; the ring fills as if the shift had been running.
   *  `picked` is the chosen start (epoch ms, 5-min grid) or null for "now". */
  let {
    picked = $bindable(null),
    dragging = $bindable(false),
    now,
    targetHours,
    disabled = false,
    onstart,
  }: {
    picked: number | null;
    dragging?: boolean;
    now: number;
    targetHours: number;
    disabled?: boolean;
    onstart: () => void;
  } = $props();

  const { size, r, stroke } = RING;
  const c = size / 2;
  const targetMs = $derived(Math.max(1, targetHours || 8) * 3_600_000);
  const maxLaps = $derived((DIAL_MAX_MIN * 60_000) / targetMs);
  const laps = $derived(picked == null ? 0 : Math.max(0, (now - picked) / targetMs));
  const knob = $derived(ringPoint(laps));
  const offsetMin = $derived(picked == null ? 0 : Math.round((now - picked) / 60_000));
  const valueText = $derived(
    picked == null
      ? 'Start now'
      : `Start ${dialDay(picked, now) ? 'yesterday ' : ''}at ${hhmm(new Date(picked))}, ${agoText(picked, now)}`,
  );

  let svg = $state<SVGSVGElement>();
  let dragLaps = 0;

  function lapsAt(e: PointerEvent, fresh = false): number {
    const b = svg!.getBoundingClientRect();
    const raw = pointerFraction(e.clientX, e.clientY, b.left + b.width / 2, b.top + b.height / 2);
    return unwrapLaps(dragLaps, raw, maxLaps, fresh);
  }

  function down(e: PointerEvent) {
    if (disabled || e.button !== 0) return;
    e.preventDefault();
    try {
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
    } catch {
      // pointer already released (synthetic events) — dragging still works while over the ring
    }
    dragging = true;
    dragLaps = laps;
    dragLaps = lapsAt(e, true);
    picked = startFromLaps(dragLaps, targetHours, Date.now());
  }
  function move(e: PointerEvent) {
    if (!dragging) return;
    dragLaps = lapsAt(e);
    picked = startFromLaps(dragLaps, targetHours, Date.now());
  }
  function up() {
    dragging = false;
  }
  // starting mid-drag (F5, Enter) unmounts the dial before any pointerup
  $effect(() => () => {
    dragging = false;
  });

  function nudge(deltaMin: number) {
    picked = nudgeStart(picked, deltaMin, Date.now());
  }

  function key(e: KeyboardEvent) {
    if (disabled) return;
    const step: Record<string, number> = {
      ArrowUp: -5,
      ArrowRight: -5,
      ArrowDown: 5,
      ArrowLeft: 5,
      PageUp: -60,
      PageDown: 60,
    };
    if (e.key in step) nudge(step[e.key]);
    else if (e.key === 'Home' || e.key === 'Escape' || e.key === 'Delete') {
      if (picked == null && e.key === 'Escape') return;
      picked = null;
    } else if (e.key === 'Enter' || e.key === ' ') onstart();
    else return;
    e.preventDefault();
    e.stopPropagation();
  }

  // non-passive so the page doesn't scroll while turning the dial
  $effect(() => {
    const el = svg?.parentElement;
    if (!el) return;
    // one mouse-wheel notch = one 5-min step; touchpads add up small deltas
    let acc = 0;
    const wheel = (e: WheelEvent) => {
      if (disabled || !e.deltaY) return;
      e.preventDefault();
      const unit = e.deltaMode === 1 ? 3 : e.deltaMode === 2 ? 1 : 100;
      if (Math.sign(acc) !== Math.sign(e.deltaY)) acc = 0;
      acc += e.deltaY / unit;
      const steps = Math.trunc(acc);
      if (!steps) return;
      acc -= steps;
      nudge(steps * 5);
    };
    el.addEventListener('wheel', wheel, { passive: false });
    return () => el.removeEventListener('wheel', wheel);
  });
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
  class="dial"
  class:dragging
  class:set={picked != null}
  class:disabled
  role="slider"
  tabindex={disabled ? -1 : 0}
  aria-label="Shift start time"
  aria-valuemin={0}
  aria-valuemax={DIAL_MAX_MIN}
  aria-valuenow={offsetMin}
  aria-valuetext={valueText}
  aria-disabled={disabled}
  onkeydown={key}
>
  <svg bind:this={svg} viewBox="0 0 {size} {size}" aria-hidden="true">
    <!-- svelte-ignore a11y_no_static_element_interactions (pointer twin of the slider's keys) -->
    <circle
      class="hit"
      cx={c}
      cy={c}
      {r}
      stroke-width={stroke + 30}
      onpointerdown={down}
      onpointermove={move}
      onpointerup={up}
      onpointercancel={up}
    />
    <g class="knob" transform="translate({knob.x} {knob.y})">
      <circle class="pulse" r={stroke / 2 + 3} />
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <circle
        class="grip"
        r={stroke / 2 + 2}
        onpointerdown={down}
        onpointermove={move}
        onpointerup={up}
        onpointercancel={up}
      />
      <circle class="pip" r="2.4" />
    </g>
  </svg>
</div>

<style>
  .dial {
    position: absolute;
    inset: 0;
    z-index: 2;
    border-radius: 50%;
    pointer-events: none;
    outline: none;
  }
  svg {
    width: 100%;
    height: 100%;
    overflow: visible;
  }
  .hit {
    fill: none;
    stroke: transparent;
    pointer-events: stroke;
    cursor: grab;
    touch-action: none;
  }
  .dragging .hit,
  .dragging .grip {
    cursor: grabbing;
  }
  .disabled .hit,
  .disabled .grip {
    pointer-events: none;
  }
  .grip {
    fill: #fff;
    stroke: hsl(var(--h2, 220) 90% 62%);
    stroke-width: 2.5;
    pointer-events: all;
    cursor: grab;
    touch-action: none;
    filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.35)) drop-shadow(0 0 8px hsl(var(--h2, 220) 100% 70% / 0.7));
    transition: r var(--dur-fast) var(--ease-out);
  }
  .knob:hover .grip,
  .dragging .grip {
    r: 11px;
  }
  .pip {
    fill: hsl(var(--h, 220) 85% 55%);
    pointer-events: none;
  }
  .pulse {
    fill: none;
    stroke: hsl(var(--h2, 220) 100% 72%);
    stroke-width: 2;
    opacity: 0;
    pointer-events: none;
    transform-box: fill-box;
    transform-origin: center;
  }
  /* hint that the live knob can be turned */
  .dial:not(.set):not(.dragging):not(.disabled) .pulse {
    animation: hint 2.6s var(--ease-out) infinite;
  }
  @keyframes hint {
    0% {
      opacity: 0.8;
      transform: scale(1);
    }
    70%,
    100% {
      opacity: 0;
      transform: scale(1.9);
    }
  }
  .dial:focus-visible .grip {
    stroke: var(--focus-ring);
    stroke-width: 4;
  }
</style>

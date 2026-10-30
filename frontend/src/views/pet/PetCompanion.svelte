<script lang="ts">
  // The Timer card's pet (docs/V2_GAMIFICATION_PLAN.md). Click to pet it;
  // right-click, a long press or the keyboard opens the pet sheet. It hops at
  // a saved shift, a Lulz milestone or an unlock, and puffs when it changes
  // pose. It sits in whichever free spot of the card is bigger, under the
  // controls or beside the ring, and hides when neither fits, so it never
  // covers the ring, the dial or the buttons.
  import { onDestroy, onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { onFx } from '../../fx/fire/fxBus';
  import { unlockQueue } from '../../lib/stores/achievements';
  import { animationsActive, motion } from '../../lib/stores/app';
  import { watchPetStats } from '../../lib/stores/pet';
  import { tooltip } from '../../lib/ui/actions';
  import { burst } from '../timer/timerActions';
  import { POSE_LABEL, type PetPose } from './petLogic';
  import { SPRITE_SIZE, openPetSheet, petSpot, petView, type PetSpot } from './petState';
  import PetSprite from './PetSprite.svelte';

  const LONG_PRESS_MS = 550;
  const PUFF = Array.from({ length: 8 }, (_, i) => i * 45);
  const SPARKS = [
    { x: 12, y: 18, d: 0 },
    { x: 84, y: 10, d: 90 },
    { x: 92, y: 52, d: 180 },
    { x: 4, y: 58, d: 260 },
  ];

  let { card, ring, controls }: { card?: HTMLElement; ring?: HTMLElement; controls?: HTMLElement } = $props();

  onMount(watchPetStats);

  let spot = $state<PetSpot | null>(null);
  let root: HTMLDivElement | undefined;
  function place() {
    if (!card || !ring || !controls) return;
    const rect = (el: HTMLElement) => el.getBoundingClientRect();
    spot = petSpot(rect(card), rect(ring), rect(controls), SPRITE_SIZE[kind]);
  }

  const v = $derived($petView);
  // petView changes every second; the observer only cares about the sprite size
  const kind = $derived(v.kind);

  // Re-place when anything around it resizes; observing every row of the card
  // also covers the controls moving when a line above them wraps.
  $effect(() => {
    if (!card || !ring || !controls) return;
    void kind;
    const ro = new ResizeObserver(place);
    for (const el of [card, ring, ...card.children]) if (el !== root) ro.observe(el);
    place();
    return () => ro.disconnect();
  });
  const full = $derived($motion === 'full');
  const label = $derived(
    `${v.name}, ${POSE_LABEL[v.pose]}${v.energy ? `, energy ${v.energy.pct}%` : ''}. Open pet`,
  );
  const fxOn = () => get(motion) === 'full' && get(animationsActive);

  let hop = $state(false);
  let squash = $state(false);
  let puff = $state(0);
  let sparks = $state(0);
  let hearts = $state<{ id: number; x: number }[]>([]);
  let heartSeq = 0;
  const timers = new Set<ReturnType<typeof setTimeout>>();
  const later = (fn: () => void, ms: number) => {
    const t = setTimeout(() => {
      timers.delete(t);
      fn();
    }, ms);
    timers.add(t);
  };
  onDestroy(() => {
    for (const t of timers) clearTimeout(t);
    clearTimeout(press);
  });

  /** Restart a one-shot animation class on the next frame. */
  function replay(set: (on: boolean) => void, ms: number) {
    set(false);
    requestAnimationFrame(() => {
      set(true);
      later(() => set(false), ms);
    });
  }

  function cheer() {
    if (!fxOn()) return;
    replay((on) => (hop = on), 650);
    sparks++;
  }

  // A new pose puffs and squashes in, but not the first one drawn after the
  // stats arrive (that's the pet appearing, not changing).
  let lastPose: PetPose | null = null;
  $effect(() => {
    const { pose, level } = v;
    if (!level) return;
    if (lastPose && pose !== lastPose && fxOn()) {
      puff++;
      replay((on) => (squash = on), 450);
    }
    lastPose = pose;
  });

  $effect(() => onFx((e) => e.kind === 'milestone' && cheer()));
  let seenBurst = get(burst);
  $effect(() => {
    if ($burst === seenBurst) return;
    seenBurst = $burst;
    cheer();
  });
  let queued = get(unlockQueue).length;
  $effect(() => {
    const n = $unlockQueue.length;
    if (n > queued) cheer();
    queued = n;
  });

  function pet() {
    if (fxOn()) replay((on) => (hop = on), 650);
    const id = ++heartSeq;
    hearts = [...hearts.slice(-3), { id, x: 30 + ((id * 37) % 40) }];
    later(() => (hearts = hearts.filter((h) => h.id !== id)), 1000);
  }

  let sheetOpen = false;
  async function open() {
    if (sheetOpen) return;
    sheetOpen = true;
    try {
      await openPetSheet();
    } finally {
      sheetOpen = false;
    }
  }

  // Long press (touch or mouse) opens the sheet; the click that follows it
  // must not also pet.
  let press: ReturnType<typeof setTimeout> | undefined;
  let pressAt: { x: number; y: number } | null = null;
  let pressed = false;
  function down(e: PointerEvent) {
    if (e.button !== 0) return;
    pressed = false;
    pressAt = { x: e.clientX, y: e.clientY };
    clearTimeout(press);
    press = setTimeout(() => {
      pressed = true;
      void open();
    }, LONG_PRESS_MS);
  }
  function move(e: PointerEvent) {
    if (pressAt && Math.hypot(e.clientX - pressAt.x, e.clientY - pressAt.y) > 8) cancel();
  }
  function cancel() {
    clearTimeout(press);
    pressAt = null;
  }
  function click(e: MouseEvent) {
    // only the pointer click that ends a long press is swallowed; a later
    // Enter (detail 0) still opens even if that click never came
    const longPress = pressed;
    pressed = false;
    if (longPress && e.detail > 0) return;
    // detail 0: Enter/Space or a screen reader, which can't long-press
    if (e.detail === 0) void open();
    else pet();
  }
  function menu(e: MouseEvent) {
    e.preventDefault();
    cancel();
    void open();
  }
</script>

<div
  class="pet"
  bind:this={root}
  hidden={!spot}
  style:left="{spot?.x ?? 0}px"
  style:top="{spot?.y ?? 0}px"
  style:width="{spot?.w ?? SPRITE_SIZE[v.kind].w}px"
  style:aspect-ratio="{SPRITE_SIZE[v.kind].w} / {SPRITE_SIZE[v.kind].h}"
>
  <button
    type="button"
    class="body"
    aria-label={label}
    use:tooltip={'Click to pet · right-click for details'}
    onclick={click}
    oncontextmenu={menu}
    onpointerdown={down}
    onpointermove={move}
    onpointerup={cancel}
    onpointercancel={cancel}
    onpointerleave={cancel}
  >
    <span class="hop" class:on={hop}>
      <span class="squash" class:on={squash}>
        <PetSprite kind={v.kind} pose={v.pose} animate={full} smooth={!!spot && spot.w < SPRITE_SIZE[v.kind].w} />
      </span>
    </span>
    {#if v.energy}
      <span class="energy" aria-hidden="true"><span style="width: {v.energy.pct}%"></span></span>
    {/if}
  </button>

  <span class="fx fx-anim" aria-hidden="true">
    {#key puff}
      {#if puff}
        {#each PUFF as a (a)}
          <span class="puff" style="--a: {a}deg"></span>
        {/each}
      {/if}
    {/key}
    {#key sparks}
      {#if sparks}
        {#each SPARKS as s, i (i)}
          <svg class="spark" style="left: {s.x}%; top: {s.y}%; animation-delay: {i * 70}ms" viewBox="0 0 5 5">
            <path d="M2 0h1v2h2v1H3v2H2V3H0V2h2z" />
          </svg>
        {/each}
      {/if}
    {/key}
    {#each hearts as h (h.id)}
      <svg class="heart" class:still={!full} style="left: {h.x}%" viewBox="0 0 7 6">
        <path d="M1 0h2v1h1V0h2v1h1v2H6v1H5v1H4v1H3V5H2V4H1V3H0V1h1z" />
      </svg>
    {/each}
  </span>
</div>

<style>
  .pet {
    position: absolute;
    z-index: 2;
  }
  .pet[hidden] {
    display: none;
  }
  .body {
    display: block;
    position: relative;
    width: 100%;
    height: 100%;
    padding: 0;
    border: 0;
    border-radius: var(--radius-md);
    background: none;
    cursor: pointer;
    touch-action: manipulation;
    -webkit-touch-callout: none;
    user-select: none;
  }
  .body:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
  }
  .hop,
  .squash {
    display: block;
    transform-origin: 50% 100%;
  }
  .hop.on {
    animation: hop 0.6s var(--ease-out);
  }
  @keyframes hop {
    35% {
      transform: translateY(-14%);
    }
    70% {
      transform: none;
    }
    82% {
      transform: scale(1.06, 0.94);
    }
  }
  .squash.on {
    animation: squash 0.42s var(--ease-spring);
  }
  @keyframes squash {
    0% {
      transform: scale(1.18, 0.82);
    }
    55% {
      transform: scale(0.94, 1.06);
    }
  }
  .energy {
    position: absolute;
    left: 30%;
    right: 30%;
    bottom: -8px;
    height: 4px;
    background: var(--divider);
    box-shadow: 0 0 0 1px color-mix(in srgb, var(--text) 18%, transparent);
  }
  .energy span {
    display: block;
    height: 100%;
    background: linear-gradient(90deg, var(--amber), #7ee787);
    transition: width var(--dur-slow) var(--ease-out);
  }

  .fx {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }
  .puff {
    position: absolute;
    left: 50%;
    top: 55%;
    width: 5px;
    height: 5px;
    margin: -2.5px;
    background: color-mix(in srgb, var(--text) 35%, white);
    animation: puff 0.5s var(--ease-out) both;
  }
  @keyframes puff {
    from {
      transform: rotate(var(--a)) translateX(10px);
    }
    to {
      transform: rotate(var(--a)) translateX(44px) scale(0.3);
      opacity: 0;
    }
  }
  .spark,
  .heart {
    position: absolute;
    shape-rendering: crispEdges;
  }
  .spark {
    width: 10px;
    height: 10px;
    fill: var(--amber);
    animation: spark 0.8s var(--ease-out) both;
  }
  @keyframes spark {
    0% {
      transform: scale(0);
    }
    40% {
      transform: scale(1.3);
    }
    100% {
      transform: scale(0.6) translateY(-10px);
      opacity: 0;
    }
  }
  .heart {
    top: 0;
    width: 14px;
    height: 12px;
    fill: #ff5d8f;
    animation: heart 1s var(--ease-out) both;
  }
  .heart.still {
    animation: none;
  }
  @keyframes heart {
    0% {
      transform: translateY(10px) scale(0.4);
      opacity: 0;
    }
    20% {
      transform: translateY(0) scale(1.15);
      opacity: 1;
    }
    100% {
      transform: translateY(-26px) scale(0.9);
      opacity: 0;
    }
  }

</style>

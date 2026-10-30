<script lang="ts">
  import { onDestroy, untrack } from 'svelte';
  import { emitFx } from '../../fx/fire/fxBus';
  import { fade, fly, reduced } from '../../lib/motion';
  import { animationsActive, lulz, motion } from '../../lib/stores/app';
  import { markShown, medalUrl, nextUnlock, openAchievements, unlockQueue } from '../../lib/stores/achievements';
  import { TIER_FX, TIER_LABEL } from './tiers';

  /** Celebrates the head of unlockQueue: a non-blocking card under the title bar
   *  with the medal flipping in. Waits a beat first so it doesn't land on top of
   *  the clock-out blast, and only counts down while the window is watched. */

  /** held: a modal is open, so don't start one now; hide the shown one and
   *  pause its countdown. waiting: a shift is on, so don't start one now, but
   *  let the shown one (already acknowledged) finish. */
  let { held = false, waiting = false }: { held?: boolean; waiting?: boolean } = $props();

  const ENTER_DELAY_MS = 900;
  const SHOW_MS = 4600;
  const TICK_MS = 100;

  let shownId = $state<string | null>(null);
  /** Where focus was before it moved into the card, to give it back on dismiss. */
  let returnFocus: HTMLElement | null = null;
  /** Focus was in the card when a modal hid it; Modal can't give it back to a removed node. */
  let refocus = false;
  let card = $state<HTMLElement>();
  /** Always-mounted live region: a freshly inserted one isn't reliably announced. */
  let announce = $state('');
  let left = SHOW_MS;
  let waitTimer: ReturnType<typeof setTimeout> | undefined;
  let tick: ReturnType<typeof setInterval> | undefined;

  const head = $derived($unlockQueue[0] ?? null);
  const current = $derived(head && head.id === shownId ? head : null);
  const more = $derived(Math.max(0, $unlockQueue.length - 1));

  $effect(() => {
    const id = head?.id ?? null;
    const wait = held || waiting;
    if (id && id === untrack(() => shownId)) return;
    clearTimeout(waitTimer);
    clearInterval(tick);
    shownId = null;
    if (!id || wait) return;
    waitTimer = setTimeout(() => show(id), ENTER_DELAY_MS);
  });

  // Before the DOM update that hides the card, while focus is still in it.
  $effect.pre(() => {
    if (held && untrack(() => card)?.contains(document.activeElement)) refocus = true;
  });
  $effect(() => {
    if (held || !refocus) return;
    refocus = false;
    const lost = !document.activeElement || document.activeElement === document.body;
    if (lost && returnFocus?.isConnected) returnFocus.focus();
  });

  /** Hovered or focused, checked live: a card hidden mid-hover never gets its pointerleave. */
  const engaged = () => !!card && (card.matches(':hover') || card.contains(document.activeElement));

  function show(id: string) {
    const a = $unlockQueue[0];
    if (!a || a.id !== id) return;
    shownId = id;
    left = SHOW_MS;
    returnFocus = null;
    announce = `Achievement unlocked: ${a.title}`;
    markShown(a);
    if ($lulz) {
      emitFx({
        kind: 'milestone',
        m: { id: `ach_${a.id}`, at: 0, tier: TIER_FX[a.tier], label: `🏆 ${a.title}`, blue: false, level: 0 },
      });
    }
    tick = setInterval(() => {
      if (held || engaged() || !$animationsActive) return;
      left -= TICK_MS;
      if (left <= 0) done();
    }, TICK_MS);
  }

  function done() {
    clearInterval(tick);
    if (card?.contains(document.activeElement) && returnFocus?.isConnected) returnFocus.focus();
    returnFocus = null;
    nextUnlock();
  }

  function focusIn(e: FocusEvent) {
    if (e.relatedTarget instanceof HTMLElement && !card?.contains(e.relatedTarget)) returnFocus = e.relatedTarget;
  }

  function view() {
    done();
    void openAchievements();
  }

  onDestroy(() => {
    clearTimeout(waitTimer);
    clearInterval(tick);
  });
</script>

<div class="sr-only" role="status" aria-live="polite">{announce}</div>

{#if current && !held}
  {#key current.id}
    <div
      bind:this={card}
      class="unlock glass glass-strong tier-{current.tier}"
      class:still={$motion === 'reduced'}
      role="group"
      aria-label="Achievement unlocked"
      onfocusin={focusIn}
      in:fly|global={{ y: -24, duration: 420 }}
      out:fade|global={{ duration: 220 }}
    >
      <button type="button" class="hit" onclick={view} aria-label="Achievement unlocked: {current.title}. View achievements">
        <span class="medal" aria-hidden="true">
          <span class="glow"></span>
          {#if !reduced()}
            <span class="sparks">{#each Array(10) as _, i (i)}<i style="--i:{i}"></i>{/each}</span>
          {/if}
          <img src={medalUrl({ ...current, hidden: false })} alt="" draggable="false" />
          <span class="shine" style="--mask: url({medalUrl({ ...current, hidden: false })})"></span>
        </span>
        <span class="text">
          <span class="kicker">Achievement unlocked{more ? ` · +${more} more` : ''}</span>
          <span class="title">{current.title}</span>
          <span class="desc">{current.desc}</span>
          <span class="chip">{TIER_LABEL[current.tier]}</span>
        </span>
      </button>
      <button type="button" class="close" aria-label="Dismiss" onclick={done}>×</button>
    </div>
  {/key}
{/if}

<style>
  .unlock {
    --tier: #d08a4a;
    position: fixed;
    top: 72px;
    left: 50%;
    translate: -50% 0;
    z-index: 150;
    width: min(420px, calc(100vw - 32px));
    display: flex;
    align-items: stretch;
    border-radius: var(--radius-lg);
    box-shadow:
      inset 0 1px 0 var(--glass-highlight),
      0 0 0 1px color-mix(in srgb, var(--tier) 45%, transparent),
      0 0 42px -8px color-mix(in srgb, var(--tier) 70%, transparent),
      var(--shadow-lg);
    overflow: visible;
  }
  .tier-silver {
    --tier: #b8c4dc;
  }
  .tier-gold {
    --tier: var(--amber);
  }
  .tier-legendary {
    --tier: var(--magenta);
  }

  .hit {
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 6px 12px 14px;
    border: 0;
    background: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
    border-radius: inherit;
  }
  .hit:focus-visible,
  .close:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: -2px;
  }

  .medal {
    position: relative;
    flex: none;
    width: 84px;
    height: 84px;
    perspective: 500px;
  }
  .medal img {
    position: relative;
    width: 100%;
    height: 100%;
    object-fit: contain;
    filter: drop-shadow(0 6px 10px rgba(0, 0, 0, 0.35));
    animation: flip-in 1100ms var(--ease-spring) both;
  }
  .glow {
    position: absolute;
    inset: -10px;
    border-radius: 50%;
    background: radial-gradient(circle, color-mix(in srgb, var(--tier) 65%, transparent) 0%, transparent 65%);
    animation: glow 2400ms ease-in-out 300ms infinite alternate both;
  }
  /* light sweep, clipped to the medal's own alpha */
  .shine {
    position: absolute;
    inset: 0;
    -webkit-mask: var(--mask) center / contain no-repeat;
    mask: var(--mask) center / contain no-repeat;
    background: linear-gradient(115deg, transparent 35%, rgba(255, 255, 255, 0.85) 50%, transparent 65%) -150% 0 / 250% 100% no-repeat;
    animation: shine 1300ms ease-out 900ms both;
    pointer-events: none;
  }
  .sparks {
    position: absolute;
    left: 50%;
    top: 50%;
  }
  .sparks i {
    position: absolute;
    width: 6px;
    height: 6px;
    margin: -3px;
    border-radius: 50%;
    background: var(--tier);
    box-shadow: 0 0 8px var(--tier);
    rotate: calc(var(--i) * 36deg);
    animation: spark 900ms cubic-bezier(0.2, 0.7, 0.3, 1) 520ms both;
  }

  .text {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .kicker {
    font-size: var(--fs-xs);
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: color-mix(in srgb, var(--tier) 70%, var(--text));
  }
  .title {
    font-size: var(--fs-lg);
    font-weight: 750;
    line-height: 1.2;
  }
  .desc {
    font-size: var(--fs-sm);
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  .chip {
    align-self: flex-start;
    margin-top: 4px;
    padding: 1px 8px;
    border-radius: 999px;
    font-size: var(--fs-xs);
    font-weight: 650;
    background: color-mix(in srgb, var(--tier) 22%, transparent);
    border: 1px solid color-mix(in srgb, var(--tier) 50%, transparent);
  }
  .close {
    flex: none;
    align-self: flex-start;
    width: 32px;
    height: 32px;
    margin: 6px;
    border: 0;
    border-radius: var(--radius-sm);
    background: none;
    color: var(--text-muted);
    font-size: 20px;
    line-height: 1;
    cursor: pointer;
  }
  .close:hover {
    color: var(--text);
    background: var(--row-hover, rgba(255, 255, 255, 0.06));
  }

  .still .medal img,
  .still .glow,
  .still .shine {
    animation: none;
  }
  .still .shine {
    display: none;
  }

  @keyframes flip-in {
    0% {
      opacity: 0;
      transform: rotateY(-540deg) scale(0.3);
    }
    35% {
      opacity: 1;
    }
    100% {
      transform: rotateY(0) scale(1);
    }
  }
  @keyframes glow {
    from {
      opacity: 0.45;
      scale: 0.9;
    }
    to {
      opacity: 1;
      scale: 1.08;
    }
  }
  @keyframes shine {
    to {
      background-position: 150% 0;
    }
  }
  @keyframes spark {
    0% {
      opacity: 1;
      transform: translateX(0) scale(1);
    }
    100% {
      opacity: 0;
      transform: translateX(58px) scale(0.3);
    }
  }
</style>

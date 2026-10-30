<script lang="ts">
  import { onDestroy, tick } from 'svelte';
  import { onFx } from '../../fx/fire/fxBus';
  import { fade, fly } from '../../lib/motion';
  import { lulz } from '../../lib/stores/motion';
  import { offerRecovery, pendingRecovery } from '../../lib/stores/recovery';
  import { settings, shifts } from '../../lib/stores/settings';
  import { elapsedSeconds, liveEarnings, timer } from '../../lib/stores/timer';
  import { formatClock, formatMoney, hhmm } from '../../lib/time';
  import { tooltip } from '../../lib/ui/actions';
  import Combobox from '../../lib/ui/Combobox.svelte';
  import Icon from '../../lib/ui/Icon.svelte';
  import Kbd from '../../lib/ui/Kbd.svelte';
  import Popover from '../../lib/ui/Popover.svelte';
  import TimePicker from '../../lib/ui/TimePicker.svelte';
  import HeroRing from './HeroRing.svelte';
  import RollingText from './RollingText.svelte';
  import StartDial from './StartDial.svelte';
  import './setup';
  import { burst, busy, jobDraft, startDialShift, startShift, stopShift, wallClock } from './timerActions';
  import {
    DIAL_RESET_MS,
    IDLE_TEXT,
    agoText,
    clockGlyphs,
    dialDay,
    fireBadge,
    haloHue,
    ringProgress,
    snapStart,
    spokenDuration,
    startedText,
  } from './timerLogic';

  const loadFire = () => import('../../fx/fire/FireLayer.svelte');

  let pickerBtn = $state<HTMLButtonElement>();
  let stage = $state<HTMLDivElement>();
  let stopBtn = $state<HTMLButtonElement>();
  let pickerOpen = $state(false);
  let celebrate = $state(false);
  let celebrateTimer: ReturnType<typeof setTimeout> | undefined;

  const running = $derived($timer.running);
  const target = $derived($settings.ui_prefs.target_hours || 8);
  // re-read with every tick so '(yesterday)' appears once midnight passes
  const startedLabel = $derived.by(() => {
    void $elapsedSeconds;
    return startedText($timer.start_iso);
  });
  /** Start picked on the idle dial (epoch ms), null = now. */
  let dialStart = $state<number | null>(null);
  let dialDragging = $state(false);
  /** When an untouched pick falls back to the live clock. */
  let dialResetAt = $state(0);
  $effect(() => {
    if (running) {
      dialStart = null;
      dialDragging = false;
    }
  });
  // every change (or grab / release) of the dial, or a start attempt ending,
  // restarts the countdown
  $effect(() => {
    void dialStart;
    void dialDragging;
    void $busy;
    dialResetAt = Date.now() + DIAL_RESET_MS;
  });
  // keep a pick at the 23h55 limit valid as the clock ticks, so what's shown
  // is what gets saved
  $effect(() => {
    if (dialStart == null) return;
    const s = snapStart(dialStart, $wallClock);
    if (s !== dialStart) dialStart = s;
  });
  $effect(() => {
    if (dialStart != null && !dialDragging && !$busy && $wallClock >= dialResetAt) dialStart = null;
  });
  const dialResetIn = $derived(Math.max(0, Math.ceil((dialResetAt - $wallClock) / 1000)));
  const dialTime = $derived(dialStart == null ? null : hhmm(new Date(dialStart)));
  const dialYesterday = $derived(dialStart != null && dialDay(dialStart, $wallClock) === 'yesterday');
  const dialWhen = $derived(dialYesterday ? `yesterday at ${dialTime}` : `at ${dialTime}`);
  // idle: the dial's back-dated head start fills the ring as a preview
  const progress = $derived(
    running
      ? ringProgress($elapsedSeconds, target)
      : dialStart == null
        ? 0
        : ringProgress(($wallClock - dialStart) / 1000, target),
  );
  /** Lulz overtime: the fire (and ring) burn white-hot blue past the target. */
  const blueFire = $derived($lulz && running && progress > 1);
  const hue = $derived($lulz && running ? (blueFire ? 205 : 28) : haloHue(progress));
  const badge = $derived($lulz ? fireBadge(running, $elapsedSeconds, target) : null);
  /** Badge pop on a Lulz milestone. */
  let flare = $state(false);
  let flareTimer: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    if (!$lulz) return;
    return onFx((e) => {
      if (e.kind !== 'milestone') return;
      flare = false;
      clearTimeout(flareTimer);
      // next frame, so a milestone during a running pop restarts it
      requestAnimationFrame(() => {
        flare = true;
        flareTimer = setTimeout(() => (flare = false), 900);
      });
    });
  });
  onDestroy(() => clearTimeout(flareTimer));
  const blocked = $derived(!!$pendingRecovery || $timer.recovery_pending);
  const pct = $derived(Math.round(progress * 100));

  let seenBurst = $burst;
  $effect(() => {
    if ($burst === seenBurst) return;
    seenBurst = $burst;
    celebrate = true;
    clearTimeout(celebrateTimer);
    celebrateTimer = setTimeout(() => (celebrate = false), 1200);
  });
  onDestroy(() => clearTimeout(celebrateTimer));

  function startAt(t: string) {
    pickerOpen = false;
    void startShift('at', t);
  }

  async function startFromDial() {
    if ($busy) return;
    const focused = stage?.contains(document.activeElement);
    await startDialShift(dialStart);
    // the dial and face button are gone now; keep keyboard focus in the timer
    await tick();
    if (focused && running) stopBtn?.focus();
  }

  function openPicker(e?: MouseEvent) {
    e?.preventDefault();
    if (!$busy) pickerOpen = true;
  }
</script>

<section class="timer glass" class:running class:lulz={$lulz} class:celebrate aria-label="Timer">
  {#if $lulz}
    <div class="fire-box" aria-hidden="true">
      {#await loadFire() then m}
        <m.default {running} elapsedSeconds={$elapsedSeconds} ring={stage} />
      {/await}
    </div>
  {/if}
  <header class="top">
    <span class="eyebrow">Timer</span>
    <span class="pill" class:on={running}>
      <span class="dot" aria-hidden="true"></span>
      {running ? 'Running' : 'Idle'}
    </span>
    {#if badge}
      {#key badge.text}
        <span class="badge" class:flare class:blue={blueFire} in:fly={{ y: -6, duration: 260 }}>
          <span aria-hidden="true">{badge.emoji}</span>
          {badge.text}
        </span>
      {/key}
    {/if}
  </header>

  <div class="stage-slot">
    <div class="stage" bind:this={stage}>
      <HeroRing {progress} {running} {hue} overHue={blueFire ? 195 : null} targetHours={target}>
        {#if running}
          <span class="ring-label">Elapsed</span>
          <span class="clock num" role="timer" aria-label={`Elapsed ${spokenDuration($elapsedSeconds)}`}>
            <RollingText text={clockGlyphs($elapsedSeconds).join('')} />
          </span>
          <span class="earn" in:fade={{ duration: 200 }}>
            <span class="money num"><RollingText text={formatMoney($liveEarnings)} /></span>
            <span class="earn-note">~{formatMoney($liveEarnings)} earned so far</span>
          </span>
          <span class="target num" in:fade={{ duration: 200 }}>{pct}% of {target}h</span>
        {:else}
          <button
            type="button"
            class="face"
            class:set={dialTime}
            disabled={$busy}
            aria-label={dialTime ? `Start the shift ${dialWhen}` : 'Start the shift now'}
            onclick={startFromDial}
          >
            <span class="ring-label">{dialTime ? (dialYesterday ? 'Yesterday at' : 'Start at') : 'Start now'}</span>
            <span class="clock num">
              <RollingText text={dialTime ?? hhmm(new Date($wallClock)) + ':' + String(new Date($wallClock).getSeconds()).padStart(2, '0')} />
            </span>
            <span class="target num">{dialStart == null ? 'tap · or turn the ring' : agoText(dialStart, $wallClock)}</span>
          </button>
        {/if}
      </HeroRing>
      {#if !running}
        <StartDial bind:picked={dialStart} bind:dragging={dialDragging} now={$wallClock} targetHours={target} disabled={$busy} onstart={startFromDial} />
      {/if}
    </div>
  </div>

  <p class="status" class:live={running} aria-live="polite">
    {#if running}
      {startedLabel}<span class="sep">·</span><strong>{$timer.job_shift || '—'}</strong><span class="sep">·</span><span class="dots">running</span>
    {:else if dialTime}
      Starts {dialYesterday ? 'yesterday at' : 'at'} <strong class="num">{dialTime}</strong><span class="sep">·</span><button
        type="button"
        class="link"
        onclick={() => (dialStart = null)}>Back to now{#if dialResetIn <= 10 && !dialDragging}<span class="num" aria-hidden="true"> ({dialResetIn}s)</span>{/if}</button
      >
    {:else}
      {IDLE_TEXT}
    {/if}
  </p>

  <div class="controls">
    {#if running}
      <button
        bind:this={stopBtn}
        class="cta stop"
        type="button"
        disabled={$busy}
        onclick={() => void stopShift('button')}
        in:fly={{ y: 8, duration: 260 }}
      >
        <span class="cta-bg" aria-hidden="true"></span>
        <Icon name="stop" size={20} />
        <span>STOP</span>
        <Kbd keys="F5" />
      </button>
      <span class="sr-only">{formatClock($elapsedSeconds)}</span>
    {:else}
      <div class="idle" in:fly={{ y: 8, duration: 260 }}>
        {#if blocked}
          <div class="blocked" role="note">
            <Icon name="warning" size={16} />
            <span>An unfinished shift needs a decision first.</span>
            <button type="button" class="link" onclick={() => void offerRecovery()}>Review</button>
          </div>
        {/if}
        <div class="job">
          <Combobox id="timer-job" label="Job / shift" bind:value={$jobDraft} options={$shifts} placeholder="Job / shift" />
        </div>
        <div class="start-row">
          <button class="cta start" type="button" disabled={$busy} onclick={() => void startShift('now')}>
            <span class="cta-bg" aria-hidden="true"></span>
            <Icon name="play" size={20} />
            <span>START NOW</span>
            <Kbd keys="F5" />
          </button>
          <div class="split" role="group" aria-label="Start at a set time">
            <button
              type="button"
              class="at"
              disabled={$busy}
              onclick={() => void startShift('at', $timer.default_start_time)}
              oncontextmenu={openPicker}
              use:tooltip={'Start from your default time (right-click to pick)'}
            >
              <span aria-hidden="true">⏰</span>
              <span class="num">{$timer.default_start_time}</span>
            </button>
            <button
              type="button"
              class="more"
              bind:this={pickerBtn}
              disabled={$busy}
              aria-label="Pick a start time"
              aria-haspopup="dialog"
              aria-expanded={pickerOpen}
              onclick={() => openPicker()}
            >
              <Icon name="chevron-down" size={16} />
            </button>
          </div>
        </div>
      </div>
    {/if}
  </div>
</section>

{#if pickerOpen}
  <Popover anchor={pickerBtn} onclose={() => (pickerOpen = false)} placement="bottom-end" label="Pick a start time">
    <TimePicker value={$timer.default_start_time} label="Start time" onpick={startAt} />
  </Popover>
{/if}

<style>
  .timer {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
    padding: 18px 22px 22px;
    border-radius: var(--radius-xl);
    overflow: hidden;
    isolation: isolate;
  }
  .top {
    align-self: stretch;
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 28px;
  }
  .eyebrow {
    font-size: var(--fs-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--text-subtle);
    margin-right: auto;
  }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 4px 10px;
    border-radius: var(--radius-pill);
    background: var(--neutral-fill);
    color: var(--text-muted);
    font-size: var(--fs-xs);
    font-weight: 600;
  }
  .pill.on {
    background: color-mix(in srgb, var(--success) 18%, transparent);
    color: var(--success-text);
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: currentColor;
    opacity: 0.6;
  }
  .pill.on .dot {
    opacity: 1;
    box-shadow: 0 0 0 0 currentColor;
    animation: pulse 1.8s var(--ease-out) infinite;
  }
  @keyframes pulse {
    0% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--success) 70%, transparent);
    }
    100% {
      box-shadow: 0 0 0 8px transparent;
    }
  }
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: var(--radius-pill);
    font-size: var(--fs-xs);
    font-weight: 700;
    /* deep enough at both ends for the light text to clear 4.5:1 */
    color: #fff7d6;
    background: linear-gradient(135deg, #b23c00, #9b1c1c);
    box-shadow: 0 4px 16px -4px rgba(255, 93, 42, 0.7);
  }
  .badge.blue {
    color: #f0f9ff;
    background: linear-gradient(135deg, #0369a1, #4338ca);
    box-shadow: 0 4px 16px -4px rgba(56, 189, 248, 0.75);
  }
  .badge.flare {
    animation: badge-flare 0.8s var(--ease-spring);
  }
  @keyframes badge-flare {
    25% {
      transform: scale(1.22) rotate(-4deg);
      filter: brightness(1.5) saturate(1.3);
      box-shadow: 0 0 22px 2px rgba(255, 209, 102, 0.85);
    }
    55% {
      transform: scale(0.96) rotate(2deg);
    }
  }
  .badge.blue.flare {
    animation-name: badge-flare-blue;
  }
  @keyframes badge-flare-blue {
    25% {
      transform: scale(1.22) rotate(-4deg);
      filter: brightness(1.5) saturate(1.3);
      box-shadow: 0 0 22px 2px rgba(125, 211, 252, 0.9);
    }
    55% {
      transform: scale(0.96) rotate(2deg);
    }
  }

  /* Gets what's left of the card's height, so on short windows (down to the
     700×560 minimum) the ring shrinks instead of the controls being clipped. */
  .stage-slot {
    align-self: stretch;
    flex: 0 1 324px;
    min-height: 150px;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    container-type: size;
  }
  .stage {
    position: relative;
    width: min(100cqw, 100cqh - 4px, 320px);
    margin-top: 4px;
    container-type: inline-size;
  }
  /* Lulz fire: the whole card, under the content, clipped to its corners */
  .fire-box {
    position: absolute;
    inset: 0;
    z-index: -1;
    border-radius: inherit;
    overflow: hidden;
    pointer-events: none;
  }
  .ring-label {
    font-size: var(--fs-xs);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: var(--text-subtle);
  }
  .clock {
    /* Sized to the ring so the digits stay inside the inner circle. */
    font-size: 13cqi;
    font-weight: 650;
    letter-spacing: -0.02em;
    line-height: 1.1;
    margin: 2px 0 4px;
    color: var(--text);
  }
  /* Glow rather than gradient text: background-clip:text can't reach the
     RollingText strips (masked/transformed layers) and they render invisible.
     drop-shadow, not text-shadow: each digit slot clips its own text-shadow
     into a visible box. */
  .running .clock {
    color: color-mix(in srgb, var(--text) 85%, var(--accent));
    filter: drop-shadow(0 0 10px color-mix(in srgb, var(--accent) 45%, transparent));
  }
  .face {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    /* fills the inner disc of the ring (r 84 of 240) */
    width: 66cqi;
    aspect-ratio: 1;
    border: 0;
    border-radius: 50%;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
    transition:
      transform var(--dur-fast) var(--ease-out),
      background var(--dur-med) var(--ease-out),
      box-shadow var(--dur-med) var(--ease-out);
  }
  .face:hover:not(:disabled) {
    background: color-mix(in srgb, var(--success) 9%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--success) 35%, transparent);
  }
  .face:hover:not(:disabled) .ring-label,
  .face.set .ring-label {
    color: var(--success-text);
  }
  .face:active:not(:disabled) {
    transform: scale(0.96);
  }
  .face:disabled {
    cursor: progress;
  }
  .face:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: -4px;
  }
  .earn {
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .money {
    font-size: var(--fs-lg);
    font-weight: 650;
    color: var(--success-text);
  }
  .earn-note {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }
  .target {
    margin-top: 4px;
    font-size: var(--fs-xs);
    color: var(--text-subtle);
  }

  .status {
    margin: 0;
    min-height: 1.4em;
    font-size: var(--fs-sm);
    color: var(--text-muted);
    text-align: center;
  }
  .status strong {
    color: var(--text);
    font-weight: 600;
  }
  .sep {
    margin: 0 8px;
    opacity: 0.5;
  }
  .dots::after {
    content: '…';
  }

  .controls {
    align-self: stretch;
    display: flex;
    flex-direction: column;
    align-items: center;
  }
  .idle {
    width: min(100%, 380px);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .blocked {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: var(--radius-sm);
    background: color-mix(in srgb, var(--amber) 14%, transparent);
    color: var(--warning-text);
    font-size: var(--fs-sm);
  }
  .blocked span {
    flex: 1;
  }
  .link {
    background: none;
    border: 0;
    padding: 2px 4px;
    color: inherit;
    font: inherit;
    font-weight: 700;
    text-decoration: underline;
    cursor: pointer;
  }
  .start-row {
    display: flex;
    gap: 10px;
  }

  .cta {
    position: relative;
    flex: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    min-height: 52px;
    padding: 0 22px;
    border: 0;
    border-radius: var(--radius-lg);
    font: inherit;
    font-size: var(--fs-md);
    font-weight: 800;
    letter-spacing: 0.08em;
    color: #fff;
    cursor: pointer;
    overflow: hidden;
    isolation: isolate;
    transition:
      transform var(--dur-fast) var(--ease-out),
      box-shadow var(--dur-med) var(--ease-out),
      filter var(--dur-fast) var(--ease-out);
  }
  .cta > :global(*) {
    position: relative;
  }
  .cta :global(.kbd),
  .cta :global(kbd) {
    opacity: 0.75;
    font-size: var(--fs-xs);
    letter-spacing: 0;
  }
  .cta-bg {
    position: absolute !important;
    inset: 0;
    z-index: -1;
    border-radius: inherit;
  }
  .start .cta-bg {
    background: linear-gradient(135deg, var(--success-strong-2), var(--success-strong) 55%, #0e9f8e);
  }
  .start {
    color: var(--on-success);
    box-shadow:
      0 10px 28px -10px var(--success-glow),
      inset 0 1px 0 rgba(255, 255, 255, 0.35);
  }
  .stop {
    width: min(100%, 380px);
    flex: none;
    min-height: 56px;
    box-shadow:
      0 12px 32px -10px var(--danger-glow),
      inset 0 1px 0 rgba(255, 255, 255, 0.25);
  }
  .stop .cta-bg {
    background: linear-gradient(135deg, #fb7185, var(--danger-strong) 55%, var(--danger-strong-2));
  }
  .cta:hover:not(:disabled) {
    transform: translateY(-2px);
    filter: brightness(1.06) saturate(1.1);
  }
  .start:hover:not(:disabled) {
    box-shadow:
      0 16px 36px -10px var(--success-glow),
      inset 0 1px 0 rgba(255, 255, 255, 0.35);
  }
  .stop:hover:not(:disabled) {
    box-shadow:
      0 16px 40px -10px var(--danger-glow),
      inset 0 1px 0 rgba(255, 255, 255, 0.25);
  }
  .cta:active:not(:disabled) {
    transform: translateY(0) scale(0.97);
  }
  .cta:disabled {
    cursor: progress;
    filter: saturate(0.6) brightness(0.9);
  }
  .cta:focus-visible,
  .split button:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 3px;
  }

  /* Lulz: STOP catches fire on hover */
  .lulz .stop::before {
    content: '';
    position: absolute;
    inset: -40% -10% 0;
    z-index: -1;
    background:
      radial-gradient(40% 60% at 20% 100%, #ffd166, transparent 70%),
      radial-gradient(35% 70% at 50% 100%, #ff9f1c, transparent 70%),
      radial-gradient(40% 60% at 80% 100%, #ff5d2a, transparent 70%);
    opacity: 0;
    transform: translateY(30%);
    transition:
      opacity var(--dur-med) var(--ease-out),
      transform var(--dur-med) var(--ease-out);
  }
  .lulz .stop:hover::before {
    opacity: 0.95;
    transform: none;
    animation: flicker 0.6s steps(3) infinite alternate;
  }
  @keyframes flicker {
    to {
      transform: translateY(-4%) scaleY(1.08);
    }
  }

  .split {
    display: flex;
    border-radius: var(--radius-lg);
    border: 1px solid var(--glass-border);
    background: var(--field-bg);
    overflow: hidden;
  }
  .split button {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: 0;
    background: transparent;
    color: var(--text);
    font: inherit;
    font-weight: 600;
    cursor: pointer;
    transition: background var(--dur-fast) var(--ease-out);
  }
  .split button:hover:not(:disabled) {
    background: var(--neutral-fill-hover);
  }
  .split button:disabled {
    opacity: 0.6;
    cursor: progress;
  }
  .at {
    padding: 0 12px 0 14px;
  }
  .more {
    padding: 0 10px;
    border-left: 1px solid var(--glass-border) !important;
    color: var(--text-muted) !important;
  }

  /* clock-out flourish */
  .celebrate .stage {
    animation: pop 0.9s var(--ease-spring);
  }
  @keyframes pop {
    30% {
      transform: scale(1.04);
    }
    100% {
      transform: none;
    }
  }

  @media (max-width: 420px) {
    .start-row {
      flex-direction: column;
    }
    .split {
      min-height: 44px;
    }
    .split .at {
      flex: 1;
      justify-content: center;
    }
  }
</style>

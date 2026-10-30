<script module lang="ts">
  import type { RingAnchor, Tier } from './fxBus';

  /** A ring anchor older than this (ms) is off screen: effects fall back to the window centre. */
  export const ANCHOR_FRESH_MS = 1000;
  /** The wizard pops this long after a blast, once the fireball has bloomed. */
  export const WIZARD_DELAY_MS = 600;

  /** Effect origin in client px: the hero ring while it is on screen, else the window centre. */
  export function fxOrigin(
    a: RingAnchor | null,
    now: number,
    W: number,
    H: number,
  ): { x: number; y: number; ring: boolean } {
    if (a && now - a.at <= ANCHOR_FRESH_MS && now >= a.at - 50 && Number.isFinite(a.x) && Number.isFinite(a.y)) {
      return { x: a.x, y: a.y, ring: true };
    }
    return { x: W / 2, y: H / 2, ring: false };
  }

  /** Blast power 0.9 … 1.3: a little bigger the longer the shift (1 when unknown). */
  export function blastPower(minutes: number | null): number {
    if (minutes == null || !Number.isFinite(minutes)) return 1;
    return 0.9 + 0.3 * Math.min(4 / 3, Math.max(0, minutes / 480));
  }

  /** Screen-shake preset key for a milestone tier. */
  export const shakeKey = (tier: Tier) => `tier${tier}` as const;

  export interface FxDevHook {
    blast(minutes?: number): void;
    milestone(tier?: Tier): void;
    ignite(): void;
    fizzle(): void;
    stats(): Record<string, unknown>;
    /** Average overlay frame work (ms) and fps over the next `ms`. */
    perf(ms?: number): Promise<{ frames: number; avgWorkMs: number; fps: number }>;
  }
</script>

<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import { isMock } from '../../lib/api';
  import { animationsActive } from '../../lib/stores/app';
  import { lulz, lulzSound, motion } from '../../lib/stores/motion';
  import { settings } from '../../lib/stores/settings';
  import { elapsedSeconds, timer } from '../../lib/stores/timer';
  import { fireIntensity } from '../../views/timer/timerLogic';
  import { SHAKE, shakeKeyframes } from './choreo';
  import FxOverlay from './FxOverlay.svelte';
  import { emitFx, getRingAnchor, onFx, type FxEvent, type Milestone } from './fxBus';
  import { createMilestoneTracker, milestonesFor } from './milestones';
  import { createFireSound } from './sound';
  import WizardPop from './WizardPop.svelte';
  import { shouldPopWizard } from './wizardPop';

  /** Lulz: app-level conductor (mounted on every route while Lulz is on). Turns
   *  timer progress into milestones and bus events into the whole-window
   *  overlay, screen shake, synthesized sound and the clock-out wizard. The
   *  ring fire itself is FireLayer's. */

  type FxWindow = Window & { __welehoFx?: FxDevHook };

  let overlay = $state<FxOverlay>();
  /** Bumped per clock-out; keys a fresh wizard pop (0 = none showing). */
  let wizardRun = $state(0);
  let wizardSeq = 0;
  let wizardTimer: ReturnType<typeof setTimeout> | null = null;
  let shakeAnim: Animation | null = null;
  /** Bumped on visibility / focus changes so the sound gate re-evaluates. */
  let focusTick = $state(0);

  const tracker = createMilestoneTracker();
  const sound = createFireSound({ makeContext: () => new AudioContext({ latencyHint: 'interactive' }) });

  const targetHours = $derived($settings.ui_prefs.target_hours);

  function origin() {
    return fxOrigin(getRingAnchor(), performance.now(), window.innerWidth, window.innerHeight);
  }

  /** Sound only while wanted, visible and focused (hidden / background windows stay silent). */
  function soundAllowed(): boolean {
    return $lulzSound && $animationsActive && document.visibilityState === 'visible' && document.hasFocus();
  }

  function shake([amp, ms]: readonly [number, number]) {
    if ($motion !== 'full' || !$animationsActive || overlay?.lowestQuality()) return;
    const el = document.querySelector<HTMLElement>('[data-fx-root]');
    if (!el || typeof el.animate !== 'function') return;
    shakeAnim?.cancel();
    shakeAnim = el.animate(shakeKeyframes(amp, ms, Math.random), { duration: ms, easing: 'linear' });
    shakeAnim.onfinish = () => (shakeAnim = null);
  }

  function popWizard() {
    if (wizardTimer !== null) clearTimeout(wizardTimer);
    wizardTimer = setTimeout(() => {
      wizardTimer = null;
      if (shouldPopWizard($lulz, $motion) && $animationsActive) wizardRun = ++wizardSeq;
    }, WIZARD_DELAY_MS);
  }

  function onBlast(minutes: number | null) {
    const o = origin();
    const power = blastPower(minutes);
    // overtime clock-outs burn blue like the ring did
    const pal = minutes != null && minutes > targetHours * 60 ? 1 : 0;
    overlay?.blast(o.x, o.y, { power, pal });
    shake(SHAKE.blast);
    sound.boom(power);
    sound.whoosh(power);
    popWizard();
  }

  function onMilestone(m: Milestone) {
    const o = origin();
    overlay?.flare(o.x, o.y, m.tier, { pal: m.blue ? 1 : 0, label: m.label });
    shake(SHAKE[shakeKey(m.tier)]);
    sound.milestone(m.tier, m.blue);
  }

  function handle(e: FxEvent) {
    switch (e.kind) {
      case 'blast':
        onBlast(e.minutes);
        break;
      case 'milestone':
        onMilestone(e.m);
        break;
      case 'fizzle': {
        const o = origin();
        overlay?.fizzle(o.x, o.y);
        sound.fizzle();
        break;
      }
      case 'ignite':
        sound.ignite(); // the ring draws the fuse
        break;
      case 'soundcheck':
        // the settings save may land before the gate effect has re-run
        sound.setEnabled(soundAllowed());
        sound.soundcheck();
        break;
    }
  }

  // Milestones: one tracker sample per elapsed tick; stopping resets it.
  // Crackle bed: only while the shift runs and the ring is on screen.
  $effect(() => {
    const running = $timer.running;
    const elapsed = $elapsedSeconds;
    const m = tracker.update(elapsed, running, targetHours);
    // handlers read stores of their own: keep them out of this effect's dependencies
    if (m) untrack(() => emitFx({ kind: 'milestone', m }));
    const onScreen = running && origin().ring;
    sound.setBed(onScreen ? fireIntensity(elapsed, targetHours) : 0, onScreen);
  });

  $effect(() => {
    void focusTick;
    sound.setEnabled(soundAllowed());
  });

  function devHook(): FxDevHook {
    return {
      blast: (minutes = 480) => emitFx({ kind: 'blast', minutes }),
      milestone: (tier = 3) => {
        const m = milestonesFor(targetHours).find((x) => x.tier === tier) ?? {
          id: `dev${tier}`,
          at: 0,
          tier,
          label: `TIER ${tier}`,
          blue: tier === 4,
          level: 0,
        };
        emitFx({ kind: 'milestone', m });
      },
      ignite: () => emitFx({ kind: 'ignite' }),
      fizzle: () => emitFx({ kind: 'fizzle' }),
      stats: () => ({
        overlay: overlay?.stats() ?? null,
        audio: sound.state,
        soundEnabled: soundAllowed(),
        origin: origin(),
      }),
      perf: (ms = 3000) => {
        const a = overlay?.stats();
        return new Promise((resolve) =>
          setTimeout(() => {
            const b = overlay?.stats();
            const frames = a && b ? b.frames - a.frames : 0;
            const work = a && b ? b.workMs - a.workMs : 0;
            resolve({ frames, avgWorkMs: frames ? work / frames : 0, fps: frames / (ms / 1000) });
          }, ms),
        );
      },
    };
  }

  onMount(() => {
    const offFx = onFx(handle);
    const bump = () => focusTick++;
    // any gesture may be the first one: let it unlock the AudioContext
    const unlock = () => sound.unlock();
    document.addEventListener('visibilitychange', bump);
    window.addEventListener('focus', bump);
    window.addEventListener('blur', bump);
    window.addEventListener('pointerdown', unlock, true);
    window.addEventListener('keydown', unlock, true);
    const w = window as FxWindow;
    const dev = import.meta.env.DEV || isMock() || new URLSearchParams(location.search).has('mock');
    if (dev) w.__welehoFx = devHook();
    return () => {
      offFx();
      document.removeEventListener('visibilitychange', bump);
      window.removeEventListener('focus', bump);
      window.removeEventListener('blur', bump);
      window.removeEventListener('pointerdown', unlock, true);
      window.removeEventListener('keydown', unlock, true);
      if (wizardTimer !== null) clearTimeout(wizardTimer);
      shakeAnim?.cancel();
      shakeAnim = null;
      tracker.reset();
      sound.dispose();
      if (dev) delete w.__welehoFx;
    };
  });
</script>

<FxOverlay bind:this={overlay} />
{#if wizardRun && shouldPopWizard($lulz, $motion)}
  {#key wizardRun}
    <WizardPop ondone={() => (wizardRun = 0)} />
  {/key}
{/if}

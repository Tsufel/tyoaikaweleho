<script lang="ts">
  // The Friday easter egg: a shift saved on a Friday (or one that started on
  // a Friday and ran past midnight) sends the pet flying across the screen on
  // its broom, stopping mid-way to say one of FRIDAY_LINES. Under reduced
  // motion it just appears mid-screen with its line for a moment. Clicks pass
  // through; the Timer companion steps out and achievement cards wait (App)
  // while petFlyby is set. The line goes to an always-mounted live region (a
  // freshly inserted one isn't reliably announced).
  import { onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import { motion } from '../../lib/stores/app';
  import { settings } from '../../lib/stores/settings';
  import { burst, savedEntry } from '../timer/timerActions';
  import { FRIDAY_LINES, fridayShift, pickLine } from './petLogic';
  import { SPRITE_SIZE, petFlyby } from './petState';
  import PetBubble from './PetBubble.svelte';
  import PetSprite from './PetSprite.svelte';

  /** The whole flight (matches the keyframes), or the still visit. */
  const FLIGHT_MS = 6000;
  const STILL_MS = 4500;

  const kind = $derived($settings.ui_prefs.pet === 'wizard' ? 'wizard' : 'familiar');
  const full = $derived($motion === 'full');

  let seen = get(burst);
  let seq = 0;
  let lastLine: string | null = null;
  let done: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    const n = $burst;
    if (n === seen) return;
    seen = n;
    if (get(settings).ui_prefs.pet === 'off' || document.visibilityState === 'hidden') return;
    if (!fridayShift(get(savedEntry), new Date())) return;
    const line = pickLine(FRIDAY_LINES, lastLine);
    lastLine = line;
    petFlyby.set({ id: ++seq, line });
    clearTimeout(done);
    done = setTimeout(() => petFlyby.set(null), get(motion) === 'full' ? FLIGHT_MS : STILL_MS);
  });
  onDestroy(() => {
    clearTimeout(done);
    petFlyby.set(null);
  });
</script>

<span class="sr-only" role="status">{$petFlyby?.line ?? ''}</span>
{#if $petFlyby}
  {#key $petFlyby.id}
    <div class="flyby" class:full aria-hidden="true">
      <div class="rider" style:width="{SPRITE_SIZE[kind].w}px">
        <span class="say"><PetBubble text={$petFlyby.line} pop={!full} /></span>
        <PetSprite {kind} pose="fly" animate={full} />
      </div>
    </div>
  {/key}
{/if}

<style>
  .flyby {
    position: fixed;
    inset: 0;
    z-index: 140;
    overflow: hidden;
    pointer-events: none;
  }
  .rider {
    position: absolute;
    left: 50%;
    top: 24%;
    transform: translateX(-50%);
  }
  .say {
    position: absolute;
    left: 50%;
    bottom: 92%;
    transform: translateX(-50%);
  }
  /* in from the left, a hover mid-screen while it talks, then off to the right
     (the broom points left, so it rides right) */
  .full .rider {
    animation: ride 6s linear both;
  }
  @keyframes ride {
    0% {
      left: 0;
      transform: translate(-100%, 48px);
      animation-timing-function: cubic-bezier(0.2, 0.7, 0.3, 1);
    }
    28% {
      left: 50%;
      transform: translate(-50%, 0);
      animation-timing-function: ease-in-out;
    }
    76% {
      left: 50%;
      transform: translate(-50%, -6px);
      animation-timing-function: cubic-bezier(0.6, 0, 0.9, 0.6);
    }
    100% {
      left: 100%;
      transform: translate(0, -72px);
    }
  }
  .full .say {
    animation: say 6s linear both;
  }
  @keyframes say {
    0%,
    27% {
      opacity: 0;
      transform: translateX(-50%) scale(0.5);
    }
    32% {
      opacity: 1;
      transform: translateX(-50%) scale(1.06);
    }
    35%,
    73% {
      opacity: 1;
      transform: translateX(-50%);
    }
    77%,
    100% {
      opacity: 0;
      transform: translateX(-50%);
    }
  }
</style>

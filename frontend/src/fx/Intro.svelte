<script lang="ts">
  import logo from '../assets/logo.webp';
  import wizard from '../assets/wizard.webp';
  import { motion } from '../lib/stores/motion';

  /** Replaces the v1.3 splash: the wizard rises in a soft glow beside the
   *  logo + wordmark, then the overlay
   *  fades. The timeline starts once `play` is set (the native window is
   *  shown); `ondone` runs once, at once under reduced motion. */
  let { ondone, version = '', play = true }: { ondone: () => void; version?: string; play?: boolean } = $props();

  let leaving = $state(false);
  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    ondone();
  };

  $effect(() => {
    if ($motion === 'reduced') finish();
  });

  $effect(() => {
    if (!play || done) return;
    const t1 = setTimeout(() => (leaving = true), 1050);
    const t2 = setTimeout(finish, 1450);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  });
</script>

<div class="intro" class:leaving class:waiting={!play} aria-hidden="true">
  <div class="wizard">
    <span class="wiz-glow"></span>
    <span class="wiz-frame"><img src={wizard} alt="" width="512" height="512" /></span>
  </div>
  <div class="brand">
    <div class="mark">
      <span class="halo"></span>
      <img src={logo} alt="" width="96" height="96" />
    </div>
    <div class="word">Työaikaweleho</div>
    {#if version}<div class="ver">v{version}</div>{/if}
  </div>
</div>

<style>
  .intro {
    position: fixed;
    inset: 0;
    z-index: 400;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: 20px 44px;
    padding: 24px;
    background: var(--bg);
    transition: opacity 380ms var(--ease-out);
  }
  .waiting * {
    animation-play-state: paused;
  }
  .leaving {
    opacity: 0;
    pointer-events: none;
  }
  .brand {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
  }
  .wizard {
    position: relative;
    display: grid;
    place-items: center;
    animation: rise-far 760ms 60ms var(--ease-out) both;
  }
  /* top of the splash art only (bubble + wizard), not its baked-in wordmark */
  .wiz-frame {
    position: relative;
    display: block;
    width: min(240px, 38vw);
    aspect-ratio: 1 / 0.68;
    overflow: hidden;
    border-radius: var(--radius-lg);
    border: 1px solid var(--glass-border);
    box-shadow: inset 0 1px 0 var(--glass-highlight), var(--shadow-md);
  }
  .wiz-frame img {
    display: block;
    width: 100%;
    height: auto;
  }
  .wiz-glow {
    position: absolute;
    inset: -48px;
    border-radius: 50%;
    background: radial-gradient(circle, var(--accent-glow), transparent 68%);
    filter: blur(8px);
    animation: glow 1100ms 120ms var(--ease-out) both;
  }
  .mark {
    position: relative;
    display: grid;
    place-items: center;
    animation: pop 700ms var(--ease-spring) both;
  }
  .mark img {
    position: relative;
    border-radius: 24px;
  }
  .halo {
    position: absolute;
    inset: -40px;
    border-radius: 50%;
    background: radial-gradient(circle, var(--accent-glow), transparent 65%);
    animation: glow 1100ms var(--ease-out) both;
  }
  .word {
    font-size: var(--fs-2xl);
    font-weight: 750;
    letter-spacing: -0.02em;
    background: linear-gradient(90deg, var(--violet), var(--cyan), var(--magenta));
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    animation: rise 600ms 180ms var(--ease-out) both;
  }
  .ver {
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
    color: var(--text-muted);
    animation: rise 600ms 300ms var(--ease-out) both;
  }
  @keyframes pop {
    from {
      opacity: 0;
      transform: scale(0.7);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
  @keyframes glow {
    from {
      opacity: 0;
      transform: scale(0.6);
    }
    60% {
      opacity: 1;
    }
    to {
      opacity: 0.7;
      transform: scale(1);
    }
  }
  @keyframes rise-far {
    from {
      opacity: 0;
      transform: translateY(36px) scale(0.94);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
  @keyframes rise {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: none;
    }
  }
</style>

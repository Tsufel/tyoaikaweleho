<script lang="ts">
  import wizard from '../../assets/wizard.webp';
  import { portal } from '../../lib/ui/actions';
  import { WIZARD_LINE, WIZARD_POP_MS } from './wizardPop';

  /** Lulz: after a saved shift the wizard pops up from the bottom-left corner
   *  with a speech bubble, then slides away. Portalled to <body> so the timer
   *  card's backdrop-filter doesn't trap the fixed position. */
  let { ondone }: { ondone: () => void } = $props();
</script>

<div
  class="wizard-pop fx-anim"
  style:--pop-ms="{WIZARD_POP_MS}ms"
  aria-hidden="true"
  use:portal
  onanimationend={(e) => {
    if (e.target === e.currentTarget) ondone();
  }}
>
  <span class="bubble glass-strong">{WIZARD_LINE}</span>
  <span class="frame"><img src={wizard} alt="" width="512" height="512" /></span>
</div>

<style>
  .wizard-pop {
    position: fixed;
    left: 20px;
    bottom: 20px;
    z-index: 250;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
    pointer-events: none;
    transform-origin: 0% 100%;
    animation: wizard-pop var(--pop-ms) var(--ease-out) both;
  }
  .frame {
    display: block;
    width: 150px;
    aspect-ratio: 1 / 0.82;
    overflow: hidden;
    border-radius: var(--radius-lg);
    border: 1px solid var(--glass-border);
    box-shadow:
      inset 0 1px 0 var(--glass-highlight),
      var(--shadow-md),
      0 0 40px -4px var(--accent-glow);
  }
  /* crop to the wizard: the art's own bubble and wordmark stay out of frame */
  .frame img {
    display: block;
    width: 200%;
    height: auto;
    margin: -39% 0 0 -93.75%;
  }
  .bubble {
    position: relative;
    margin-left: 34px;
    padding: 8px 14px;
    border-radius: var(--radius-md);
    font-weight: 700;
    white-space: nowrap;
    color: var(--text);
    animation: bubble var(--pop-ms) var(--ease-spring) both;
  }
  .bubble::after {
    content: '';
    position: absolute;
    left: 22px;
    bottom: -7px;
    width: 12px;
    height: 12px;
    background: inherit;
    border-right: 1px solid var(--glass-border);
    border-bottom: 1px solid var(--glass-border);
    transform: rotate(45deg);
  }
  @keyframes wizard-pop {
    0% {
      opacity: 0;
      transform: translate(-40px, 60px) scale(0.6) rotate(-8deg);
    }
    14% {
      opacity: 1;
      transform: translate(0, -6px) scale(1.04) rotate(2deg);
    }
    20% {
      transform: none;
    }
    80% {
      opacity: 1;
      transform: none;
    }
    100% {
      opacity: 0;
      transform: translate(-180px, 30px) rotate(-6deg);
    }
  }
  @keyframes bubble {
    0%,
    16% {
      opacity: 0;
      transform: translateY(8px) scale(0.7);
    }
    26%,
    76% {
      opacity: 1;
      transform: none;
    }
    86%,
    100% {
      opacity: 0;
      transform: translateY(-4px) scale(0.9);
    }
  }
</style>

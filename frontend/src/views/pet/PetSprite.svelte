<script lang="ts">
  // One pet pose with a small pixel-art idle loop: the body breathes (the rows
  // above a seam drop a pixel and come back), nods off while drowsy and
  // hovers while flying; the sparkles twinkle and the z's float up. Moves go
  // in whole art pixels, in steps, like a frame-by-frame sprite. Shared by the
  // Timer companion and the pet sheet. Loops only run with full motion and
  // pause with the app (.fx-anim); otherwise it's the plain picture.
  import type { PetPose } from './petLogic';
  import { SPRITE_SIZE, spriteUrl, type PetView } from './petState';
  import { spriteLayers } from './petSpriteLayers';

  let {
    kind,
    pose,
    animate,
    scale = 1,
    smooth = false,
  }: {
    kind: PetView['kind'];
    pose: PetPose;
    animate: boolean;
    scale?: number;
    /** Drawn below 1×: blend pixels instead of dropping some. */
    smooth?: boolean;
  } = $props();

  const size = $derived(SPRITE_SIZE[kind]);
  const src = $derived(spriteUrl(kind, pose));
  const parts = $derived(animate ? spriteLayers(kind, pose, size) : null);
</script>

<!-- --px / --pxx: one art pixel (2 sprite px) as a share of the sprite, which
     is what translate() percentages on the full-size copies refer to -->
<span
  class="sprite fx-anim pose-{pose}"
  class:loop={!!parts}
  class:smooth
  style="--w: {size.w * scale}px; --ar: {size.w} / {size.h}; --px: calc(200% / {size.h}); --pxx: calc(200% / {size.w})"
  aria-hidden="true"
>
  <span class="shadow"></span>
  {#if parts}
    {#each parts.layers as layer (layer.part)}
      <img class={layer.part} {src} alt="" draggable="false" style:clip-path={layer.clip} />
    {/each}
    {#each parts.bits as bit, i (i)}
      <img class={bit.kind} {src} alt="" draggable="false" style:clip-path={bit.clip} style:--phase={bit.phase} />
    {/each}
  {:else}
    <img {src} alt="" draggable="false" />
  {/if}
</span>

<style>
  .sprite {
    position: relative;
    display: block;
    width: 100%;
    max-width: var(--w);
    aspect-ratio: var(--ar);
  }
  img {
    position: absolute;
    inset: 0;
    display: block;
    width: 100%;
    height: 100%;
    image-rendering: pixelated;
    user-select: none;
    -webkit-user-drag: none;
  }
  .smooth img {
    image-rendering: auto;
  }
  .shadow {
    position: absolute;
    left: 22%;
    right: 22%;
    bottom: 1%;
    height: 7%;
    border-radius: 50%;
    background: radial-gradient(closest-side, rgba(0, 0, 0, 0.28), transparent);
  }
  .pose-fly .shadow {
    left: 32%;
    right: 32%;
    bottom: -4%;
    opacity: 0.6;
  }

  /* step-end: each keyframe's pose holds until the next one, no in-betweens */
  .pose-idle .upper {
    animation: breathe 1.8s step-end infinite;
  }
  .pose-sleep .upper {
    animation: breathe 3.6s step-end infinite;
  }
  .pose-drowsy .upper {
    animation: nod 3.2s step-end infinite;
  }
  .pose-fly .whole {
    animation: hover 1.6s step-end infinite;
  }
  .loop.pose-fly .shadow {
    animation: shadow 1.6s step-end infinite;
  }
  .spark {
    animation: twinkle 2.4s step-end infinite;
    animation-delay: calc(var(--phase) * -2.4s);
  }
  .pose-fly .spark {
    animation: trail 1.6s step-end infinite;
    animation-delay: calc(var(--phase) * -1.6s);
  }
  .z {
    animation: float 3s step-end infinite;
    animation-delay: calc(var(--phase) * 3s);
  }

  @keyframes breathe {
    50%,
    100% {
      transform: translateY(var(--px));
    }
  }
  @keyframes nod {
    40% {
      transform: translateY(var(--px));
    }
    55% {
      transform: translateY(calc(var(--px) * 2));
    }
    90%,
    100% {
      transform: none;
    }
  }
  @keyframes hover {
    25%,
    75% {
      transform: translateY(calc(var(--px) * -1));
    }
    50% {
      transform: translateY(calc(var(--px) * -2));
    }
    100% {
      transform: none;
    }
  }
  @keyframes shadow {
    25%,
    75% {
      transform: scaleX(0.9);
    }
    50% {
      transform: scaleX(0.8);
    }
    100% {
      transform: none;
    }
  }
  @keyframes twinkle {
    70% {
      opacity: 0.3;
    }
    80%,
    100% {
      opacity: 1;
    }
  }
  @keyframes trail {
    30% {
      transform: translateX(calc(var(--pxx) * -1));
    }
    60% {
      transform: translateX(calc(var(--pxx) * -2));
      opacity: 0.6;
    }
    85%,
    100% {
      transform: translateX(calc(var(--pxx) * -3));
      opacity: 0;
    }
  }
  @keyframes float {
    16% {
      transform: translateY(calc(var(--px) * -1));
    }
    33% {
      transform: translate(var(--pxx), calc(var(--px) * -2));
    }
    50% {
      transform: translate(var(--pxx), calc(var(--px) * -3));
    }
    66% {
      transform: translateY(calc(var(--px) * -4));
      opacity: 0.7;
    }
    80% {
      transform: translateY(calc(var(--px) * -5));
      opacity: 0.35;
    }
    90%,
    100% {
      transform: translateY(calc(var(--px) * -5));
      opacity: 0;
    }
  }
</style>

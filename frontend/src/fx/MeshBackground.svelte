<!-- Aurora mesh: five soft blobs drifting on CSS transforms (compositor
     only, no JS per frame). Paused via :root[data-paused] and static under
     :root[data-motion='reduced'] (global.css). -->
<div class="mesh fx-anim" aria-hidden="true">
  <span class="blob b1"></span>
  <span class="blob b2"></span>
  <span class="blob b3"></span>
  <span class="blob b4"></span>
  <span class="blob b5"></span>
</div>

<style>
  .mesh {
    position: fixed;
    inset: 0;
    z-index: 0;
    overflow: hidden;
    pointer-events: none;
    background:
      radial-gradient(120% 90% at 50% 0%, var(--bg-2), transparent 70%),
      var(--bg);
    contain: strict;
  }
  /* The softness is baked into the gradient (the radial profile of a cone
     blurred by 70px) instead of a blur filter: a filtered layer is re-blurred
     every frame it moves, and under glass every backdrop-filter re-samples it. */
  .blob {
    position: absolute;
    width: 62vmax;
    height: 62vmax;
    background: radial-gradient(
      circle,
      color-mix(in srgb, var(--c) 80%, transparent) 0%,
      color-mix(in srgb, var(--c) 76%, transparent) 10%,
      color-mix(in srgb, var(--c) 65%, transparent) 20%,
      color-mix(in srgb, var(--c) 51%, transparent) 30%,
      color-mix(in srgb, var(--c) 36%, transparent) 40%,
      color-mix(in srgb, var(--c) 22%, transparent) 50%,
      color-mix(in srgb, var(--c) 10%, transparent) 60%,
      color-mix(in srgb, var(--c) 3%, transparent) 70%,
      transparent 80%
    );
    will-change: transform;
    animation: drift 38s ease-in-out infinite alternate;
  }
  .b1 {
    --c: var(--mesh-1);
    left: -18vmax;
    top: -22vmax;
  }
  .b2 {
    --c: var(--mesh-2);
    right: -22vmax;
    top: -10vmax;
    animation-duration: 46s;
    animation-delay: -12s;
  }
  .b3 {
    --c: var(--mesh-3);
    left: 18vmax;
    bottom: -30vmax;
    animation-duration: 52s;
    animation-delay: -20s;
    animation-name: drift2;
  }
  .b4 {
    --c: var(--mesh-4);
    right: -14vmax;
    bottom: -26vmax;
    width: 48vmax;
    height: 48vmax;
    animation-duration: 42s;
    animation-delay: -6s;
    animation-name: drift2;
  }
  .b5 {
    --c: var(--mesh-5);
    left: -12vmax;
    bottom: -18vmax;
    width: 44vmax;
    height: 44vmax;
    animation-duration: 58s;
    animation-delay: -30s;
  }
  @keyframes drift {
    0% {
      transform: translate3d(0, 0, 0) scale(1);
    }
    50% {
      transform: translate3d(9vmax, 6vmax, 0) scale(1.12);
    }
    100% {
      transform: translate3d(-5vmax, 11vmax, 0) scale(0.94);
    }
  }
  @keyframes drift2 {
    0% {
      transform: translate3d(0, 0, 0) scale(1.05);
    }
    50% {
      transform: translate3d(-10vmax, -7vmax, 0) scale(0.92);
    }
    100% {
      transform: translate3d(6vmax, -12vmax, 0) scale(1.1);
    }
  }
  :global(:root[data-motion='reduced']) .blob {
    animation: none !important;
  }
</style>

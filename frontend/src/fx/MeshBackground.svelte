<script lang="ts">
  /** Aurora mesh: five blurred blobs drifting on CSS transforms (compositor
   *  only, no JS per frame). Paused via :root[data-paused] and static under
   *  :root[data-motion='reduced'] (global.css). */
  const NOISE =
    "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.5 0 0 0 0 0.5 0 0 0 0 0.5 0 0 0 1 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")";
</script>

<div class="mesh fx-anim" aria-hidden="true">
  <span class="blob b1"></span>
  <span class="blob b2"></span>
  <span class="blob b3"></span>
  <span class="blob b4"></span>
  <span class="blob b5"></span>
  <span class="noise" style:background-image={NOISE}></span>
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
  .blob {
    position: absolute;
    width: 62vmax;
    height: 62vmax;
    border-radius: 50%;
    filter: blur(70px);
    will-change: transform;
    animation: drift 38s ease-in-out infinite alternate;
  }
  .b1 {
    background: radial-gradient(circle, var(--mesh-1), transparent 65%);
    left: -18vmax;
    top: -22vmax;
  }
  .b2 {
    background: radial-gradient(circle, var(--mesh-2), transparent 65%);
    right: -22vmax;
    top: -10vmax;
    animation-duration: 46s;
    animation-delay: -12s;
  }
  .b3 {
    background: radial-gradient(circle, var(--mesh-3), transparent 65%);
    left: 18vmax;
    bottom: -30vmax;
    animation-duration: 52s;
    animation-delay: -20s;
    animation-name: drift2;
  }
  .b4 {
    background: radial-gradient(circle, var(--mesh-4), transparent 65%);
    right: -14vmax;
    bottom: -26vmax;
    width: 48vmax;
    height: 48vmax;
    animation-duration: 42s;
    animation-delay: -6s;
    animation-name: drift2;
  }
  .b5 {
    background: radial-gradient(circle, var(--mesh-5), transparent 65%);
    left: -12vmax;
    bottom: -18vmax;
    width: 44vmax;
    height: 44vmax;
    animation-duration: 58s;
    animation-delay: -30s;
  }
  .noise {
    position: absolute;
    inset: 0;
    opacity: var(--noise-opacity);
    mix-blend-mode: overlay;
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

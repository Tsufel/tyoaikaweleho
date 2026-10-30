<script lang="ts">
  // A pixel-art speech bubble over the pet, its tail pointing down at it. Pops
  // in with full motion, otherwise just appears. Placed by the parent, which
  // can nudge the tail with --tail-shift when it moves the bubble off-centre.
  // Decorative: the parent announces the line if it should be heard.
  let { text, pop = true }: { text: string; pop?: boolean } = $props();
</script>

<span class="bubble" class:pop aria-hidden="true">{text}</span>

<style>
  .bubble {
    position: relative;
    display: block;
    width: max-content;
    max-width: 260px;
    padding: 5px 10px 6px;
    border: 2px solid #1d1a2b;
    border-radius: 4px;
    background: #fffdf5;
    box-shadow: 3px 3px 0 color-mix(in srgb, #1d1a2b 30%, transparent);
    color: #1d1a2b;
    font-size: 13px;
    font-weight: 700;
    line-height: 1.25;
    text-align: center;
    pointer-events: none;
    transform-origin: 50% 100%;
  }
  /* the tail: two stepped pixel blocks, outline under fill */
  .bubble::before,
  .bubble::after {
    content: '';
    position: absolute;
    left: calc(50% + var(--tail-shift, 0px));
    top: 100%;
  }
  .bubble::before {
    width: 12px;
    height: 10px;
    margin-left: -6px;
    background: #1d1a2b;
    clip-path: polygon(0 0, 100% 0, 100% 40%, 66% 40%, 66% 80%, 33% 80%, 33% 100%, 0 100%);
  }
  .bubble::after {
    width: 8px;
    height: 6px;
    margin: -2px 0 0 -4px;
    background: #fffdf5;
    clip-path: polygon(0 0, 100% 0, 100% 33%, 50% 33%, 50% 100%, 0 100%);
  }
  .pop {
    animation: pop 0.32s var(--ease-spring) both;
  }
  @keyframes pop {
    from {
      transform: scale(0.5);
      opacity: 0;
    }
  }
</style>

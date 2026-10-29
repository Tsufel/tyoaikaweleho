<script lang="ts">
  import { Tween } from 'svelte/motion';
  import { cubicOut } from 'svelte/easing';
  import { reduced } from '../lib/motion';

  /** Counts up/down to `value` (instant under reduced motion). The final text is exposed to AT. */
  let {
    value,
    format,
    duration = 900,
    delay = 0,
  }: { value: number; format: (n: number) => string; duration?: number; delay?: number } = $props();

  const tween = new Tween(0, { easing: cubicOut });
  let first = true;

  $effect(() => {
    const v = value;
    const d = reduced() ? 0 : duration;
    void tween.set(v, { duration: d, delay: first && !reduced() ? delay : 0 });
    first = false;
  });
</script>

<span class="roll num" aria-hidden="true">{format(tween.current)}</span><span class="sr-only">{format(value)}</span>

<style>
  .roll {
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
</style>

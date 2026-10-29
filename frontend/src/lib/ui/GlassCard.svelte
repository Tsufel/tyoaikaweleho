<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLAttributes } from 'svelte/elements';

  interface Props extends Omit<HTMLAttributes<HTMLElement>, 'children'> {
    /** More opaque fill (dialogs, popovers). */
    strong?: boolean;
    /** Lift + brighter border on hover. */
    interactive?: boolean;
    padding?: string;
    radius?: 'md' | 'lg' | 'xl';
    tag?: 'div' | 'section' | 'article' | 'aside' | 'header' | 'footer' | 'nav';
    el?: HTMLElement;
    children?: Snippet;
  }

  let {
    strong = false,
    interactive = false,
    padding = '20px',
    radius = 'lg',
    tag = 'div',
    el = $bindable(),
    class: cls = '',
    children,
    ...rest
  }: Props = $props();
</script>

<svelte:element
  this={tag}
  bind:this={el}
  class="glass card r-{radius} {cls}"
  class:glass-strong={strong}
  class:interactive
  style:padding
  {...rest}
>
  {@render children?.()}
</svelte:element>

<style>
  .card {
    position: relative;
  }
  .r-md {
    border-radius: var(--radius-md);
  }
  .r-xl {
    border-radius: var(--radius-xl);
  }
  .interactive {
    transition:
      transform var(--dur-med) var(--ease-out),
      box-shadow var(--dur-med) var(--ease-out),
      border-color var(--dur-med) var(--ease-out);
  }
  .interactive:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--accent) 35%, var(--glass-border));
    box-shadow: inset 0 1px 0 var(--glass-highlight), var(--shadow-lg);
  }
</style>

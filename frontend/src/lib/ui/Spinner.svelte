<script lang="ts">
  let { size = 18, label }: { size?: number; label?: string } = $props();
</script>

<span
  class="spinner"
  style:width="{size}px"
  style:height="{size}px"
  role={label ? 'status' : undefined}
  aria-label={label}
  aria-hidden={label ? undefined : 'true'}
></span>

<style>
  .spinner {
    display: inline-block;
    flex: none;
    border-radius: 50%;
    border: 2px solid currentColor;
    border-right-color: transparent;
    opacity: 0.85;
    animation: spin 0.7s linear infinite;
  }
  /* keep spinning under reduced motion (it carries meaning), just slower */
  :global(:root[data-motion='reduced']) .spinner {
    animation: spin 1.4s linear infinite !important;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>

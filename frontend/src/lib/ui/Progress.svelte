<script lang="ts">
  /** value 0–1, or null for indeterminate. */
  let { value = null, label, tone = 'accent' }: { value?: number | null; label: string; tone?: 'accent' | 'success' | 'danger' } =
    $props();
  const pct = $derived(value === null ? null : Math.round(Math.min(1, Math.max(0, value)) * 100));
</script>

<div
  class="progress {tone}"
  class:indeterminate={pct === null}
  role="progressbar"
  aria-label={label}
  aria-valuemin={0}
  aria-valuemax={100}
  aria-valuenow={pct ?? undefined}
>
  <div class="bar" style:width={pct === null ? undefined : `${pct}%`}></div>
</div>

<style>
  .progress {
    position: relative;
    height: 6px;
    border-radius: var(--radius-pill);
    background: var(--neutral-fill);
    overflow: hidden;
  }
  .bar {
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--accent-strong), var(--cyan));
    transition: width var(--dur-med) var(--ease-out);
  }
  .success .bar {
    background: linear-gradient(90deg, var(--success-strong), var(--teal));
  }
  .danger .bar {
    background: linear-gradient(90deg, var(--danger-strong), var(--magenta));
  }
  .indeterminate .bar {
    width: 40%;
    animation: slide 1.2s var(--ease-out) infinite;
  }
  @keyframes slide {
    from {
      transform: translateX(-100%);
    }
    to {
      transform: translateX(260%);
    }
  }
</style>

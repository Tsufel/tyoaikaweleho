<script lang="ts">
  import type { Snippet } from 'svelte';
  import { Icon, tooltip, type IconName } from '../../lib/ui';
  import RollingNumber from '../../charts/RollingNumber.svelte';
  import type { KpiDelta } from '../../charts/chartUtils';

  let {
    icon,
    label,
    value,
    format,
    tone = 'violet',
    delay = 0,
    delta = null,
    sub,
  }: {
    icon: IconName;
    label: string;
    value: number;
    format: (n: number) => string;
    tone?: 'violet' | 'cyan' | 'magenta' | 'amber' | 'teal';
    delay?: number;
    /** Change from the previous period, shown beside the value. */
    delta?: KpiDelta | null;
    sub?: Snippet;
  } = $props();
</script>

<article class="tile glass tone-{tone}">
  <div class="head">
    <span class="badge" aria-hidden="true"><Icon name={icon} size={16} /></span>
    <h3>{label}</h3>
  </div>
  <div class="value-row">
    <p class="value"><RollingNumber {value} {format} {delay} /></p>
    {#if delta}
      <span class="delta {delta.tone}" use:tooltip={delta.hint}>
        <span class="delta-text" aria-hidden="true">
          {#if delta.tone !== 'even'}<Icon name={delta.tone === 'up' ? 'chevron-up' : 'chevron-down'} size={12} />{/if}
          <span class="num">{delta.text}</span>
        </span>
        <span class="sr-only">{delta.hint}</span>
      </span>
    {/if}
  </div>
  {#if sub}<div class="sub">{@render sub()}</div>{/if}
</article>

<style>
  .tile {
    --tone: var(--violet);
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
    padding: 16px 18px 15px;
    border-radius: var(--radius-lg);
    transition:
      transform var(--dur-med) var(--ease-out),
      box-shadow var(--dur-med) var(--ease-out),
      border-color var(--dur-med) var(--ease-out);
  }
  .tile::before {
    content: '';
    position: absolute;
    inset: -40% -30% auto auto;
    width: 140px;
    height: 140px;
    border-radius: 50%;
    background: radial-gradient(closest-side, color-mix(in srgb, var(--tone) 34%, transparent), transparent);
    opacity: 0.7;
    pointer-events: none;
    transition: opacity var(--dur-med) var(--ease-out);
  }
  .tile:hover {
    transform: translateY(-3px);
    border-color: color-mix(in srgb, var(--tone) 40%, var(--glass-border));
    box-shadow:
      inset 0 1px 0 var(--glass-highlight),
      0 10px 34px -10px color-mix(in srgb, var(--tone) 55%, transparent),
      var(--shadow-md);
  }
  .tile:hover::before {
    opacity: 1;
  }
  .tone-cyan {
    --tone: var(--cyan);
  }
  .tone-magenta {
    --tone: var(--magenta);
  }
  .tone-amber {
    --tone: var(--amber);
  }
  .tone-teal {
    --tone: var(--teal);
  }
  .head {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .badge {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 9px;
    color: var(--text);
    background: color-mix(in srgb, var(--tone) 24%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--tone) 40%, transparent);
  }
  h3 {
    margin: 0;
    font-size: var(--fs-sm);
    font-weight: 600;
    color: var(--text-muted);
    overflow-wrap: anywhere;
  }
  .value {
    margin: 2px 0 0;
    font-family: var(--font-mono);
    font-size: clamp(1.35rem, 2.1vw, 1.75rem);
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--text);
    line-height: 1.15;
  }
  .value-row {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 4px 10px;
    min-width: 0;
  }
  .delta {
    display: inline-flex;
    flex: none;
    font-size: var(--fs-xs);
    font-weight: 650;
    color: var(--text-subtle);
    cursor: default;
  }
  .delta-text {
    display: inline-flex;
    align-items: center;
    gap: 2px;
  }
  .delta.up {
    color: var(--success-text);
  }
  .delta.down {
    color: var(--danger-text);
  }
  .sub {
    font-size: var(--fs-xs);
    color: var(--text-subtle);
    min-height: 1.3em;
  }

  /* Liquid glass: keep the tone glow and border on hover over the liquid
     float shadow ((0,6,0) beats liquid.css's .glass.tile:hover) */
  :global(:root[data-glass='liquid']) .tile.glass:hover {
    border-color: color-mix(in srgb, var(--tone) 40%, var(--glass-border));
    box-shadow:
      inset 0 1px 0 var(--glass-highlight),
      inset 0 0 20px -8px var(--lg-inner),
      inset 0 -1px 0 var(--lg-well),
      0 10px 34px -10px color-mix(in srgb, var(--tone) 55%, transparent),
      var(--lg-shadow-float);
  }
</style>

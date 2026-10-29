<script lang="ts">
  import Icon, { type IconName } from '../../lib/ui/Icon.svelte';

  /** Big choice button for confirm renderers: icon, title, one-line description. */
  let {
    id,
    title,
    description = '',
    icon,
    tone = 'neutral',
    hint = '',
    onpick,
  }: {
    id: string;
    title: string;
    description?: string;
    icon: IconName;
    tone?: 'primary' | 'danger' | 'success' | 'neutral';
    /** Small right-aligned tag, e.g. a key hint or time. */
    hint?: string;
    onpick: (id: string) => void;
  } = $props();
</script>

<button type="button" class="card tone-{tone}" data-choice={id} onclick={() => onpick(id)}>
  <span class="badge" aria-hidden="true"><Icon name={icon} size={19} /></span>
  <span class="text">
    <span class="title">{title}</span>
    {#if description}<span class="desc">{description}</span>{/if}
  </span>
  {#if hint}<span class="hint mono">{hint}</span>{/if}
  <span class="chev" aria-hidden="true"><Icon name="chevron-right" size={16} /></span>
</button>

<style>
  .card {
    --tone: var(--text-muted);
    --tone-bg: var(--neutral-fill);
    position: relative;
    display: flex;
    align-items: center;
    gap: 14px;
    width: 100%;
    padding: 13px 14px 13px 13px;
    border-radius: var(--radius-md);
    border: 1px solid var(--glass-border);
    background: var(--field-bg);
    color: var(--text);
    text-align: left;
    cursor: pointer;
    transition:
      transform var(--dur-fast) var(--ease-out),
      border-color var(--dur-fast) var(--ease-out),
      background var(--dur-fast) var(--ease-out),
      box-shadow var(--dur-med) var(--ease-out);
  }
  .card:hover {
    background: var(--field-bg-focus);
    border-color: color-mix(in srgb, var(--tone) 45%, var(--glass-border));
    transform: translateY(-1px);
    box-shadow: 0 8px 24px -10px color-mix(in srgb, var(--tone) 55%, transparent);
  }
  .card:active {
    transform: translateY(0) scale(0.99);
  }
  .card:focus-visible {
    outline: 2px solid var(--focus-ring);
    outline-offset: 2px;
    border-color: color-mix(in srgb, var(--tone) 60%, var(--glass-border));
  }
  .tone-primary {
    --tone: var(--accent);
    --tone-bg: color-mix(in srgb, var(--accent) 18%, transparent);
  }
  .tone-success {
    --tone: var(--success);
    --tone-bg: color-mix(in srgb, var(--success) 18%, transparent);
  }
  .tone-danger {
    --tone: var(--danger);
    --tone-bg: color-mix(in srgb, var(--danger) 16%, transparent);
  }
  .badge {
    flex: none;
    display: grid;
    place-items: center;
    width: 38px;
    height: 38px;
    border-radius: 12px;
    background: var(--tone-bg);
    color: var(--tone);
  }
  .tone-neutral .badge {
    color: var(--text-muted);
  }
  .text {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .title {
    font-weight: 600;
    font-size: var(--fs-md);
  }
  .tone-danger .title {
    color: var(--danger-text);
  }
  .desc {
    color: var(--text-muted);
    font-size: var(--fs-sm);
    line-height: 1.4;
  }
  .hint {
    flex: none;
    font-size: var(--fs-xs);
    color: var(--text-subtle);
    padding: 3px 8px;
    border-radius: var(--radius-pill);
    background: var(--neutral-fill);
  }
  .chev {
    flex: none;
    color: var(--text-subtle);
    opacity: 0;
    transform: translateX(-4px);
    transition:
      opacity var(--dur-fast) var(--ease-out),
      transform var(--dur-fast) var(--ease-out);
  }
  .card:hover .chev,
  .card:focus-visible .chev {
    opacity: 1;
    transform: none;
  }
</style>

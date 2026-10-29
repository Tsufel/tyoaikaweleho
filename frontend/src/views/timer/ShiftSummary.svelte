<script lang="ts">
  import { elapsedSeconds, timer } from '../../lib/stores/timer';
  import { formatDuration, formatMoney, fromIsoDateTime, hhmm, strftime } from '../../lib/time';

  /** Started / elapsed / earned strip for stop and close confirms. Ticks live
   *  when `startIso` is the running shift, else uses `elapsedMinutes`. */
  let {
    startIso,
    elapsedMinutes = 0,
    job = '',
    tone = 'accent',
  }: { startIso: string; elapsedMinutes?: number; job?: string; tone?: 'accent' | 'warning' | 'danger' } = $props();

  const start = $derived(fromIsoDateTime(startIso));
  const live = $derived($timer.running && $timer.start_iso === startIso);
  const minutes = $derived(live ? Math.floor($elapsedSeconds / 60) : elapsedMinutes);
  const earned = $derived((minutes / 60) * ($timer.pay_rate || 0));
  const sameDay = $derived(start ? start.toDateString() === new Date().toDateString() : true);
</script>

<div class="summary tone-{tone}">
  <div class="cell">
    <span class="k">Started</span>
    <span class="v num">{start ? hhmm(start) : '—'}</span>
    <span class="s">{start ? (sameDay ? 'today' : strftime(start, '%a %d %b')) : ''}</span>
  </div>
  <div class="cell">
    <span class="k">Elapsed</span>
    <span class="v num">{formatDuration(minutes)}</span>
    <span class="s">{job || ' '}</span>
  </div>
  <div class="cell">
    <span class="k">Earned</span>
    <span class="v num">{formatMoney(earned)}</span>
    <span class="s">@ {formatMoney($timer.pay_rate || 0)}/h</span>
  </div>
</div>

<style>
  .summary {
    --tone: var(--accent);
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1px;
    border-radius: var(--radius-md);
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--tone) 28%, var(--glass-border));
    background: color-mix(in srgb, var(--tone) 22%, var(--glass-border));
    margin-bottom: 14px;
  }
  .tone-warning {
    --tone: var(--amber);
  }
  .tone-danger {
    --tone: var(--danger);
  }
  .cell {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 10px 12px;
    background: color-mix(in srgb, var(--tone) 7%, var(--glass-solid));
    min-width: 0;
  }
  .k {
    font-size: var(--fs-xs);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-subtle);
  }
  .v {
    font-size: var(--fs-lg);
    font-weight: 650;
    color: var(--text);
  }
  .s {
    font-size: var(--fs-xs);
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>

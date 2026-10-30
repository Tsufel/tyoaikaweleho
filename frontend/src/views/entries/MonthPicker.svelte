<script lang="ts">
  import { MONTHS, MONTHS_SHORT } from '../../lib/time';
  import Button from '../../lib/ui/Button.svelte';
  import Field from '../../lib/ui/Field.svelte';
  import Icon from '../../lib/ui/Icon.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import TextInput from '../../lib/ui/TextInput.svelte';
  import { parseYear, pickerStep, stepMonth } from './entriesLogic';

  /** "Go to month" (v1.3 MonthPickerDialog): ↑/↓ step the month,
   *  PgUp/PgDn the year, Enter jumps, Esc cancels. */
  let {
    year,
    month,
    onpick,
    oncancel,
  }: { year: number; month: number; onpick: (y: number, m: number) => void; oncancel: () => void } = $props();

  const now = new Date();
  const init = () => ({ y: year, m: month });
  let m = $state(init().m);
  let yearText = $state(String(init().y));
  let yearError = $state<string | null>(null);
  const y = $derived(parseYear(yearText));

  function step(delta: number) {
    const base = y ?? init().y;
    const n = stepMonth(base, m, delta);
    m = n.month;
    yearText = String(n.year);
    yearError = null;
  }

  function go() {
    if (y === null) {
      yearError = 'Enter a year between 1900 and 9999.';
      return;
    }
    onpick(y, m);
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.ctrlKey || e.altKey || e.metaKey) return;
    const d = pickerStep(e.key);
    if (d !== null) {
      e.preventDefault();
      e.stopPropagation();
      step(d);
    } else if (e.key === 'Enter') {
      const t = e.target as HTMLElement;
      if (t.tagName === 'BUTTON') return;
      e.preventDefault();
      e.stopPropagation();
      go();
    }
  }
</script>

<Modal title="Go to month" icon="info" size="sm" onclose={oncancel} closeButton initialFocus="#mp-year">
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div class="picker" onkeydown={onKeydown}>
    <div class="current" aria-live="polite">
      <button type="button" class="step lg-gel" aria-label="Previous month" onclick={() => step(-1)}>
        <Icon name="chevron-left" size={18} />
      </button>
      <span class="label">{MONTHS[m - 1]} <span class="num">{y ?? yearText}</span></span>
      <button type="button" class="step lg-gel" aria-label="Next month" onclick={() => step(1)}>
        <Icon name="chevron-right" size={18} />
      </button>
    </div>

    <div class="grid" role="radiogroup" aria-label="Month">
      {#each MONTHS_SHORT as name, i (name)}
        {@const n = i + 1}
        <button
          type="button"
          role="radio"
          aria-checked={n === m}
          aria-label={MONTHS[i]}
          class:selected={n === m}
          class:today={y === now.getFullYear() && n === now.getMonth() + 1}
          tabindex={n === m ? 0 : -1}
          onclick={() => (m = n)}
          ondblclick={() => (m = n, go())}
        >
          {name}
        </button>
      {/each}
    </div>

    <Field label="Year" forId="mp-year" error={yearError} hint="↑/↓ month · PgUp/PgDn year · Enter to go">
      <TextInput
        id="mp-year"
        bind:value={yearText}
        mono
        inputmode="numeric"
        maxlength={4}
        invalid={!!yearError}
        aria-describedby="mp-year-note"
        oninput={() => (yearError = null)}
      />
    </Field>
  </div>

  {#snippet footer()}
    <Button variant="secondary" onclick={oncancel}>Cancel</Button>
    <Button variant="primary" glow icon="calendar" onclick={go}>Go</Button>
  {/snippet}
</Modal>

<style>
  .picker {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .current {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .label {
    font-size: var(--fs-lg);
    font-weight: 650;
    letter-spacing: -0.01em;
  }
  .num {
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
  }
  .step {
    display: grid;
    place-items: center;
    width: 34px;
    height: 34px;
    border-radius: var(--radius-pill);
    border: 1px solid var(--glass-border);
    background: var(--neutral-fill);
    color: var(--text);
    cursor: pointer;
    transition:
      background var(--dur-fast) var(--ease-out),
      transform var(--dur-fast) var(--ease-out);
  }
  .step:hover {
    background: var(--neutral-fill-hover);
  }
  .step:active {
    transform: scale(0.94);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px;
  }
  .grid button {
    position: relative;
    padding: 9px 0;
    border-radius: var(--radius-md);
    border: 1px solid transparent;
    background: var(--neutral-fill);
    color: var(--text);
    font: inherit;
    font-size: var(--fs-sm);
    cursor: pointer;
    transition:
      background var(--dur-fast) var(--ease-out),
      box-shadow var(--dur-fast) var(--ease-out),
      transform var(--dur-fast) var(--ease-out);
  }
  .grid button:hover {
    background: var(--neutral-fill-hover);
    transform: translateY(-1px);
  }
  .grid button:active {
    transform: scale(0.97);
  }
  .grid button.today {
    border-color: var(--accent);
  }
  .grid button.selected {
    background: var(--accent-strong);
    color: #fff;
    box-shadow: 0 4px 16px -4px var(--accent-glow);
  }
  button:focus-visible {
    outline: none;
    box-shadow: 0 0 0 3px var(--focus-ring);
  }

  /* Liquid glass: clear chip (icon only) with gel press */
  :global(:root[data-glass='liquid']) .step {
    background: linear-gradient(180deg, var(--lg-sheen), transparent 60%), var(--lg-clear);
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }
  :global(:root[data-glass='liquid']) .step:hover {
    background: linear-gradient(180deg, var(--lg-sheen), transparent 60%), var(--neutral-fill-hover);
  }
  /* the inset highlight above outranks button:focus-visible: keep the ring */
  :global(:root[data-glass='liquid']) .step:focus-visible {
    box-shadow: inset 0 1px 0 var(--glass-highlight), 0 0 0 3px var(--focus-ring);
  }
  :global(:root[data-glass='liquid']:not([data-motion='reduced'])) .step.lg-gel {
    transition:
      background var(--dur-fast) var(--ease-out),
      transform var(--dur-fast) var(--ease-out),
      scale 460ms var(--lg-spring);
  }
  :global(:root[data-glass='liquid']:not([data-motion='reduced'])) .step.lg-gel:active {
    transform: none;
    scale: 1.06 0.94;
    transition-duration: var(--dur-fast), var(--dur-fast), 90ms;
  }
</style>

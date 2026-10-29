<script lang="ts">
  /** Odometer text: each digit is a 0–9 strip sliding to its value. Keyed from
   *  the right so "9:59" → "10:00" rolls instead of re-mounting. Visual only:
   *  the parent supplies the accessible text. */
  let { text, class: cls = '' }: { text: string; class?: string } = $props();

  const DIGITS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
  const chars = $derived([...text]);
</script>

<span class="roll {cls}" aria-hidden="true">
  {#each chars as c, i (chars.length - i)}
    {#if c >= '0' && c <= '9'}
      <span class="slot">
        <span class="strip" style:transform="translateY({-Number(c) * 10}%)">
          {#each DIGITS as d (d)}<span class="digit">{d}</span>{/each}
        </span><span class="sizer">0</span>
      </span>
    {:else}
      <span class="sep">{c}</span>
    {/if}
  {/each}
</span>

<style>
  .roll {
    display: inline-flex;
    align-items: baseline;
    font-variant-numeric: tabular-nums;
    white-space: pre;
  }
  .slot {
    position: relative;
    display: inline-block;
    overflow: hidden;
    height: 1.15em;
    line-height: 1.15em;
    vertical-align: bottom;
    white-space: nowrap;
    mask-image: linear-gradient(180deg, transparent 0, #000 14%, #000 86%, transparent 100%);
  }
  .sizer {
    visibility: hidden;
  }
  .strip {
    position: absolute;
    left: 0;
    top: 0;
    display: flex;
    flex-direction: column;
    transition: transform 380ms cubic-bezier(0.2, 0.8, 0.2, 1);
    will-change: transform;
  }
  .digit {
    display: block;
    height: 1.15em;
    text-align: center;
  }
  .sep {
    display: inline-block;
    line-height: 1.15em;
  }
</style>

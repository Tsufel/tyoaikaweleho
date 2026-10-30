<script lang="ts">
  let {
    checked = $bindable(false),
    label,
    id,
    disabled = false,
    describedby,
    onchange,
  }: {
    checked?: boolean;
    label: string;
    id?: string;
    disabled?: boolean;
    describedby?: string;
    onchange?: (v: boolean) => void;
  } = $props();

  function toggle() {
    if (disabled) return;
    checked = !checked;
    onchange?.(checked);
  }
</script>

<button
  {id}
  type="button"
  role="switch"
  class="switch"
  aria-checked={checked}
  aria-label={label}
  aria-describedby={describedby}
  {disabled}
  onclick={toggle}
>
  <span class="thumb"></span>
</button>

<style>
  .switch {
    position: relative;
    flex: none;
    width: 44px;
    height: 26px;
    padding: 0;
    border: 1px solid var(--field-border);
    border-radius: var(--radius-pill);
    background: var(--neutral-fill);
    cursor: pointer;
    transition:
      background-color var(--dur-fast),
      border-color var(--dur-fast);
  }
  .switch[aria-checked='true'] {
    background: linear-gradient(135deg, var(--accent-strong), var(--accent-strong-2));
    border-color: transparent;
  }
  .thumb {
    position: absolute;
    top: 3px;
    left: 3px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #fff;
    box-shadow: var(--shadow-sm);
    transition: transform var(--dur-med) var(--ease-spring);
  }
  .switch[aria-checked='true'] .thumb {
    transform: translateX(18px);
  }
  .switch:disabled {
    opacity: 0.5;
    cursor: default;
  }

  /* Liquid glass: a glossy thumb that turns to clear gel while pressed */
  :global(:root[data-glass='liquid']) .thumb {
    box-shadow: var(--shadow-sm), inset 0 -1px 0 rgba(0, 0, 0, 0.12);
  }
  :global(:root[data-glass='liquid']:not([data-motion='reduced'])) .thumb {
    transition:
      transform var(--dur-med) var(--ease-spring),
      scale 460ms var(--lg-spring),
      background-color var(--dur-fast);
  }
  :global(:root[data-glass='liquid']:not([data-motion='reduced'])) .switch:not(:disabled):active .thumb {
    scale: 1.18 1;
    background: rgba(255, 255, 255, 0.6);
    transition-duration: var(--dur-med), 90ms, 90ms;
  }
</style>

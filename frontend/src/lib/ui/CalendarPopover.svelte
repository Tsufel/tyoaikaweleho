<script lang="ts">
  import Calendar from './Calendar.svelte';
  import Popover from './Popover.svelte';

  let {
    anchor,
    value = null,
    onpick,
    onclose,
  }: {
    anchor: HTMLElement | null | undefined;
    value?: string | null;
    onpick: (iso: string) => void;
    onclose: () => void;
  } = $props();
</script>

<Popover {anchor} {onclose} label="Choose date" placement="bottom-start">
  <Calendar
    {value}
    onpick={(iso) => {
      onpick(iso);
      onclose();
      anchor?.focus();
    }}
  />
</Popover>

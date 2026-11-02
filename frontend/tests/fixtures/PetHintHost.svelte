<script lang="ts">
  // The offer as TimerView mounts it: gone once answered, with a START button to land on.
  import { settings } from '../../src/lib/stores/settings';
  import PetHint from '../../src/views/pet/PetHint.svelte';

  let card = $state<HTMLElement>();
</script>

<section bind:this={card}>
  <button type="button" class="cta start">START NOW</button>
  {#if !$settings.ui_prefs.pet_hint_seen}<PetHint {card} />{/if}
</section>

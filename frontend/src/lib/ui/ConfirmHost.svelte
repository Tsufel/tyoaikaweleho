<script lang="ts">
  import { dialogs } from '../stores/confirm';
  import ChoiceModal from './ChoiceModal.svelte';
</script>

<!-- Renders confirm requests, alerts and sheets (stores/confirm). Mounted once by App. -->
{#each $dialogs as d (d.id)}
  {#if d.type === 'choice'}
    {#if d.renderer}
      <d.renderer request={d.request} onchoose={d.resolve} />
    {:else}
      <ChoiceModal request={d.request} onchoose={d.resolve} />
    {/if}
  {:else}
    <d.component {...d.props} onclose={d.resolve} />
  {/if}
{/each}

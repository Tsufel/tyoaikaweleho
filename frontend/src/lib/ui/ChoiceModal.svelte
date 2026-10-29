<script lang="ts">
  import type { ChoiceRequest } from '../stores/confirm';
  import Button, { type ButtonVariant } from './Button.svelte';
  import Modal from './Modal.svelte';

  /** Generic confirm / message box (v1.3 ui/msgbox): Enter = focused button
   *  (the default first), ←/→ move between buttons, Escape = request.cancel. */
  let { request, onchoose }: { request: ChoiceRequest; onchoose: (id: string) => void } = $props();

  const msgId = `choice-msg-${Math.random().toString(36).slice(2, 8)}`;
  let row = $state<HTMLDivElement>();
  let done = false;

  function pick(id: string) {
    if (done) return;
    done = true;
    onchoose(id);
  }

  const variantOf = (v: string | undefined, id: string): ButtonVariant =>
    v === 'danger' ? 'danger' : v === 'primary' || (!v && id === request.default) ? 'primary' : 'secondary';

  function onKeydown(e: KeyboardEvent) {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    const btns = [...(row?.querySelectorAll<HTMLButtonElement>('button') ?? [])];
    const i = btns.indexOf(document.activeElement as HTMLButtonElement);
    if (i < 0) return;
    e.preventDefault();
    const next = (i + (e.key === 'ArrowRight' ? 1 : -1) + btns.length) % btns.length;
    btns[next].focus();
  }
</script>

<Modal
  title={request.title}
  icon={request.icon}
  size="sm"
  role="alertdialog"
  describedby={msgId}
  initialFocus={`[data-choice="${request.default}"]`}
  onclose={() => pick(request.cancel)}
>
  <p id={msgId} class="msg">{request.message}</p>
  {#snippet footer()}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="row" bind:this={row} onkeydown={onKeydown}>
      {#each request.options as o (o.id)}
        <Button variant={variantOf(o.variant, o.id)} data-choice={o.id} onclick={() => pick(o.id)}>
          {o.label}
        </Button>
      {/each}
    </div>
  {/snippet}
</Modal>

<style>
  .msg {
    white-space: pre-line;
    color: var(--text-muted);
    line-height: 1.55;
    font-size: var(--fs-md);
  }
  .row {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 10px;
  }
</style>

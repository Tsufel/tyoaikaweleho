<script lang="ts">
  // The Timer card's one-time offer of a work pet, shown while the pet is off
  // and the offer hasn't been answered. Any answer sets `pet_hint_seen`, and a
  // toast says where the setting lives, so the offer never comes back.
  import { tick } from 'svelte';
  import type { PetKind } from '../../lib/api/types';
  import { fly } from '../../lib/motion';
  import { navigate } from '../../lib/stores/app';
  import { saveUiPrefs } from '../../lib/stores/settings';
  import { toast } from '../../lib/stores/toasts';
  import Button from '../../lib/ui/Button.svelte';
  import { DEFAULT_PET_NAME } from './petLogic';
  import PetSprite from './PetSprite.svelte';

  const WHERE = 'Settings ▸ Effects ▸ Pet';

  let { card }: { card?: HTMLElement } = $props();

  let el = $state<HTMLDivElement>();
  let busy = $state(false);

  const shown = (host: HTMLElement | undefined, sel: string) => {
    const target = host?.querySelector<HTMLElement>(sel);
    return target && !target.closest('[hidden]') ? target : null;
  };
  const frame = () => new Promise((r) => requestAnimationFrame(r));

  /** The strip unmounts as soon as it's answered (the save is optimistic):
   *  keep keyboard focus in the card, on `first` or else the START/STOP button. */
  async function refocus(host: HTMLElement | undefined, first: string) {
    await tick();
    if (document.activeElement && document.activeElement !== document.body) return;
    (shown(host, first) ?? shown(host, '.cta.start, .cta.stop'))?.focus();
  }

  /** The pet hides when the card has no room for it (narrow two-column
   *  windows); wait for it to be placed, so the toast doesn't greet a no-show. */
  async function petPlaced(host: HTMLElement | undefined): Promise<boolean> {
    if (!host) return true;
    await tick();
    await frame();
    await frame();
    return !!shown(host, 'button.body');
  }

  async function answer(kind: PetKind | null, e: MouseEvent) {
    if (busy) return;
    busy = true;
    const host = card;
    // keyboard activation clicks with detail 0; a mouse click leaves focus be
    const keyboard = e.detail === 0 && !!el?.contains(document.activeElement);
    const ok = await saveUiPrefs(kind ? { pet: kind, pet_hint_seen: true } : { pet_hint_seen: true });
    busy = false;
    // a failed save brings the strip back: return to its first button
    if (keyboard) void refocus(host, ok ? (kind ? 'button.body' : '.cta.start') : '.pet-hint button');
    if (!ok) return;
    if (kind && kind !== 'off') {
      const name = DEFAULT_PET_NAME[kind];
      if (await petPlaced(host)) {
        toast(`Say hi to ${name}! Rename or switch your pet in ${WHERE}`, { tone: 'success' });
      } else {
        toast(`${name} is ready but needs more room: make the window a bit bigger to see it on the Timer card`);
      }
    } else {
      toast(`You can get a work pet any time in ${WHERE}`, {
        label: 'Open Settings',
        action: () => void navigate('settings'),
        undo: false,
      });
    }
  }
</script>

<div class="pet-hint" role="group" bind:this={el} aria-labelledby="pet-hint-title" in:fly={{ y: 10 }}>
  <span class="art" aria-hidden="true"><PetSprite kind="familiar" pose="idle" animate={false} scale={0.3} smooth /></span>
  <p class="text">
    <strong id="pet-hint-title">Want a work pet?</strong>
    <span class="sub">It keeps you company and charges up as you log hours.</span>
  </p>
  <div class="actions">
    <Button size="sm" variant="primary" disabled={busy} onclick={(e) => answer('familiar', e)}>Familiar</Button>
    <Button size="sm" disabled={busy} onclick={(e) => answer('wizard', e)}>Wizard</Button>
    <Button
      size="sm"
      variant="ghost"
      square
      icon="x"
      label="No thanks"
      tooltip="No thanks"
      disabled={busy}
      onclick={(e) => answer(null, e)}
    />
  </div>
</div>

<style>
  .pet-hint {
    align-self: stretch;
    margin-top: auto;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px 10px;
    padding: 8px 8px 8px 10px;
    border-radius: var(--radius-lg);
    background: var(--neutral-fill);
    border: 1px solid var(--glass-border);
  }
  .art {
    flex: none;
    display: grid;
    place-items: center;
    width: 44px;
    height: 38px;
    overflow: hidden;
  }
  .text {
    flex: 1 1 180px;
    min-width: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
    font-size: var(--fs-sm);
    color: var(--text);
  }
  .sub {
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
  /* drops under the text when the card is narrow */
  .actions {
    flex: none;
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  /* short windows: one row, so the ring keeps its room and nothing is clipped */
  @media (max-height: 700px) {
    .pet-hint {
      flex-wrap: nowrap;
    }
    .art,
    .sub {
      display: none;
    }
  }
</style>

<script lang="ts">
  // The pet up close: level and rank, energy and lifetime hours, and its looks
  // (petSkins.ts), which unlock by level. Opened from the Timer companion
  // (openPetSheet); naming and switching live in Settings.
  import { onMount } from 'svelte';
  import { refreshPetStats, watchPetStats } from '../../lib/stores/pet';
  import Button from '../../lib/ui/Button.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import Spinner from '../../lib/ui/Spinner.svelte';
  import { motion, navigate } from '../../lib/stores/app';
  import { saveUiPrefs, settings } from '../../lib/stores/settings';
  import { tooltip } from '../../lib/ui/actions';
  import type { PetPose } from './petLogic';
  import { PET_SKINS, isUnlocked, previewPose, skinMoments, type SkinInfo } from './petSkins';
  import { SPRITE_SIZE, fmtHours, petView } from './petState';
  import PetSprite from './PetSprite.svelte';

  let { onclose }: { onclose: (r: void) => void } = $props();

  onMount(() => {
    const stop = watchPetStats();
    void refreshPetStats();
    return stop;
  });

  const v = $derived($petView);

  const MOOD: Record<PetPose, string> = {
    idle: 'is awake and ready for the next shift.',
    fly: 'is flying along with your shift.',
    drowsy: "is getting sleepy: today's target is almost done.",
    sleep: 'is asleep. Starting a shift wakes it up.',
  };
  // Drowsy starts at TIRED_AT (75%) of the target, so only overtime is "past" it.
  const mood = $derived(v.pose === 'drowsy' && v.overtime ? "is getting sleepy: you're past today's target." : MOOD[v.pose]);

  /** What a look's card says under its name. */
  function lookNote(s: SkinInfo, level: number): string {
    if (!isUnlocked(s, level)) return `Level ${s.level}`;
    if (s.id === 'classic') return 'The original';
    const when = skinMoments(v.kind, s.id);
    return when ? `When ${when}` : '';
  }

  // Compared with the stored choice, not the look drawn: a chosen look whose
  // level is no longer reached draws classic, and picking Classic then must
  // still save, or the old look would come back on its own.
  const chosen = $derived($settings.ui_prefs.pet_skin);
  let saving = $state(false);
  async function wear(s: SkinInfo) {
    if (saving || s.id === chosen || !v.level || !isUnlocked(s, v.level.level)) return;
    saving = true;
    await saveUiPrefs({ pet_skin: s.id });
    saving = false;
  }

  function openSettings() {
    onclose();
    void navigate('settings');
  }
</script>

<Modal title={v.name} size="md" onclose={() => onclose()} closeButton class="pet-sheet">
  <div class="hero">
    <div class="stage">
      <PetSprite kind={v.kind} pose={v.pose} skin={v.skin} bazooka={v.bazooka} animate={$motion === 'full'} scale={2} />
    </div>
    <p class="mood"><strong>{v.name}</strong> {mood}</p>
  </div>

  {#if v.level && v.energy}
    <div class="meters">
      <div class="meter">
        <div class="row">
          <span class="title">Level {v.level.level} · {v.level.rank}</span>
          <span class="num">{fmtHours(v.level.hours)} h logged</span>
        </div>
        <span
          class="bar xp"
          role="progressbar"
          aria-label="Progress to level {v.level.level + 1}"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(v.level.progress * 100)}
        ><span style="width: {v.level.progress * 100}%"></span></span>
        <span class="note">{fmtHours(Math.max(0, v.level.next - v.level.hours))} h to level {v.level.level + 1}</span>
      </div>
      <div class="meter">
        <div class="row">
          <span class="title">Energy</span>
          <span class="num">{v.energy.pct}%</span>
        </div>
        <span
          class="bar energy"
          role="progressbar"
          aria-label="Energy"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={v.energy.pct}
        ><span style="width: {v.energy.pct}%"></span></span>
        <span class="note">{fmtHours(v.energy.hours)} h of {fmtHours(v.energy.goal)} h in the last 7 days. Days off never drain it.</span>
        {#if v.streak >= 2}
          <span class="streak">🔥 {v.streak} workdays at target in a row</span>
        {/if}
      </div>
    </div>

    {@const lvl = v.level.level}
    <section class="looks" aria-labelledby="pet-looks-title">
      <h3 id="pet-looks-title">Looks</h3>
      <div class="grid" aria-busy={saving}>
        {#each PET_SKINS as s (s.id)}
          {@const open = isUnlocked(s, lvl)}
          <button
            type="button"
            class="look"
            class:locked={!open}
            aria-pressed={s.id === v.skin}
            aria-disabled={!open}
            use:tooltip={open ? s.blurb[v.kind] : `Reach level ${s.level} to unlock: ${s.blurb[v.kind]}`}
            onclick={() => wear(s)}
          >
            <span class="preview">
              <PetSprite
                kind={v.kind}
                pose={previewPose(v.kind, s.id)}
                skin={s.id}
                animate={false}
                scale={64 / SPRITE_SIZE[v.kind].w}
                smooth
              />
            </span>
            <span class="name">{s.label}</span>
            <span class="sub">{#if !open}<span class="sr-only">{'Unlocks at '}</span>{/if}{lookNote(s, lvl)}</span>
          </button>
        {/each}
      </div>
    </section>
  {:else}
    <div class="center"><Spinner size={22} label="Loading" /></div>
  {/if}

  <p class="where">New looks unlock as {v.name} levels up. Rename or switch your pet in Settings ▸ Effects ▸ Pet.</p>

  {#snippet footer()}
    <Button onclick={openSettings}>Pet settings</Button>
    <Button variant="primary" onclick={() => onclose()} data-autofocus>Close</Button>
  {/snippet}
</Modal>

<style>
  .hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    margin-bottom: 16px;
  }
  .stage {
    display: flex;
    justify-content: center;
    width: 100%;
    max-width: 330px;
    padding: 18px 0 6px;
  }
  .mood {
    margin: 0;
    text-align: center;
    color: var(--text-muted);
  }
  .mood strong {
    color: var(--text);
  }
  .meters {
    display: flex;
    flex-direction: column;
    gap: 14px;
    margin-top: 16px;
  }
  .meter {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .row {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
  }
  .title {
    font-weight: 700;
  }
  .num {
    font-variant-numeric: tabular-nums;
    color: var(--text-muted);
    font-size: var(--fs-sm);
  }
  .note {
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
  .bar {
    position: relative;
    height: 8px;
    border-radius: 999px;
    background: var(--divider);
    overflow: hidden;
  }
  .bar > span {
    position: absolute;
    inset: 0 auto 0 0;
    border-radius: inherit;
    transition: width var(--dur-slow) var(--ease-out);
  }
  .streak {
    align-self: flex-start;
    margin-top: 2px;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: var(--fs-xs);
    font-weight: 600;
    background: color-mix(in srgb, var(--amber) 16%, transparent);
    border: 1px solid color-mix(in srgb, var(--amber) 40%, transparent);
  }
  .xp > span {
    background: linear-gradient(90deg, var(--violet), var(--magenta));
  }
  .energy > span {
    background: linear-gradient(90deg, var(--amber), #3fb950);
  }
  .looks {
    margin-top: 20px;
  }
  .looks h3 {
    margin: 0 0 8px;
    font-size: var(--fs-sm);
    font-weight: 700;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
    gap: 8px;
  }
  .look {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 8px 6px;
    border-radius: var(--radius-lg);
    border: 1px solid var(--glass-border);
    background: var(--neutral-fill);
    color: var(--text);
    font: inherit;
    cursor: pointer;
    transition:
      border-color var(--dur-fast) var(--ease-out),
      background var(--dur-fast) var(--ease-out);
  }
  .look:hover:not([aria-disabled='true']) {
    border-color: var(--violet);
  }
  .look[aria-pressed='true'] {
    border-color: var(--violet);
    background: color-mix(in srgb, var(--violet) 14%, transparent);
    cursor: default;
  }
  .look[aria-disabled='true'] {
    cursor: default;
  }
  .preview {
    display: grid;
    place-items: center;
    width: 64px;
    height: 60px;
  }
  .locked .preview {
    filter: grayscale(1) brightness(0.35);
    opacity: 0.6;
  }
  .name {
    font-size: var(--fs-sm);
    font-weight: 700;
  }
  .sub {
    font-size: var(--fs-xs);
    color: var(--text-muted);
    text-align: center;
  }
  .locked .name,
  .locked .sub {
    color: var(--text-muted);
  }
  .where {
    margin: 16px 0 0;
    font-size: var(--fs-xs);
    color: var(--text-muted);
  }
  .center {
    display: grid;
    place-items: center;
    padding: 24px;
  }
</style>

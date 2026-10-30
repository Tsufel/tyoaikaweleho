<script lang="ts">
  // The pet up close: its name (editable), level and rank, energy and lifetime
  // hours. Opened from the Timer companion (openPetSheet).
  import { onMount } from 'svelte';
  import { refreshPetStats, watchPetStats } from '../../lib/stores/pet';
  import { settings } from '../../lib/stores/settings';
  import Button from '../../lib/ui/Button.svelte';
  import Field from '../../lib/ui/Field.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import Spinner from '../../lib/ui/Spinner.svelte';
  import TextInput from '../../lib/ui/TextInput.svelte';
  import { motion } from '../../lib/stores/app';
  import { DEFAULT_PET_NAME, PET_NAME_MAX, type PetPose } from './petLogic';
  import { commitPetName, fmtHours, petView } from './petState';
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
    drowsy: "is getting sleepy: you're past today's target.",
    sleep: 'is asleep. Starting a shift wakes it up.',
  };

  let draft = $state($settings.ui_prefs.pet_name);
  let input = $state<HTMLInputElement>();
  // follow a rename made elsewhere (Settings), unless the user is typing here
  $effect(() => {
    const saved = $settings.ui_prefs.pet_name;
    if (document.activeElement !== input) draft = saved;
  });
  async function save() {
    const sent = draft;
    const saved = await commitPetName(sent);
    // keep anything typed while the save was in flight
    if (draft === sent) draft = saved;
  }
</script>

<Modal title={v.name} size="md" onclose={() => onclose()} closeButton class="pet-sheet">
  <div class="hero">
    <div class="stage">
      <PetSprite kind={v.kind} pose={v.pose} animate={$motion === 'full'} scale={2} />
    </div>
    <p class="mood"><strong>{v.name}</strong> {MOOD[v.pose]}</p>
  </div>

  <Field label="Name" forId="pet-name" hint="Up to {PET_NAME_MAX} characters. Leave empty for {DEFAULT_PET_NAME[v.kind]}.">
    <TextInput
      id="pet-name"
      bind:value={draft}
      bind:el={input}
      maxlength={PET_NAME_MAX}
      placeholder={DEFAULT_PET_NAME[v.kind]}
      autocomplete="off"
      spellcheck="false"
      aria-describedby="pet-name-note"
      onblur={save}
      onkeydown={(e: KeyboardEvent) => e.key === 'Enter' && (e.preventDefault(), void save())}
    />
  </Field>

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
      </div>
    </div>
  {:else}
    <div class="center"><Spinner size={22} label="Loading" /></div>
  {/if}

  {#snippet footer()}
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
  .xp > span {
    background: linear-gradient(90deg, var(--violet), var(--magenta));
  }
  .energy > span {
    background: linear-gradient(90deg, var(--amber), #3fb950);
  }
  .center {
    display: grid;
    place-items: center;
    padding: 24px;
  }
</style>

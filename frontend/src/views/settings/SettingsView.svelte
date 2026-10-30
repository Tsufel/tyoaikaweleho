<script lang="ts">
  import { onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import wizard from '../../assets/wizard.webp';
  import { emitFx } from '../../fx/fire/fxBus';
  import { api } from '../../lib/api';
  import type { Appearance, ExportFormat } from '../../lib/api/types';
  import { fly, stagger } from '../../lib/motion';
  import { registerCommand } from '../../lib/shortcuts';
  import { bootstrap, navigate } from '../../lib/stores/app';
  import { alert, askYesNoCancel, reportError } from '../../lib/stores/confirm';
  import { refreshMonth } from '../../lib/stores/entries';
  import { prefersReducedMotion } from '../../lib/stores/motion';
  import { applySettings, dlc, saveUiPrefs, settings, shifts } from '../../lib/stores/settings';
  import { refreshTimer } from '../../lib/stores/timer';
  import { toast } from '../../lib/stores/toasts';
  import { parsePayRate } from '../../lib/time';
  import { appearancePreview } from '../../lib/theme/theme';
  import Button from '../../lib/ui/Button.svelte';
  import Combobox from '../../lib/ui/Combobox.svelte';
  import Field, { describedBy } from '../../lib/ui/Field.svelte';
  import GlassCard from '../../lib/ui/GlassCard.svelte';
  import Icon, { type IconName } from '../../lib/ui/Icon.svelte';
  import Kbd from '../../lib/ui/Kbd.svelte';
  import Segmented from '../../lib/ui/Segmented.svelte';
  import Switch from '../../lib/ui/Switch.svelte';
  import TextInput from '../../lib/ui/TextInput.svelte';
  import TimeInput from '../../lib/ui/TimeInput.svelte';
  import {
    checkOutcome,
    clampTarget,
    dlcView,
    fieldOf,
    formatTarget,
    formFromSettings,
    isDirty,
    draftFromForm,
    payPreview,
    SHORTCUTS,
    TARGET_MAX,
    TARGET_MIN,
    TARGET_STEP,
    type CheckState,
    type FormField,
  } from './settingsLogic';
  import { dlcBusy, installDlc, promptUpdate, removeDlc } from './updateFlow';

  const initial = formFromSettings(get(settings));
  let form = $state({ ...initial });
  let errors = $state<Partial<Record<FormField, string>>>({});
  let saving = $state(false);
  let leaving = false;
  let check = $state<CheckState>({ kind: 'idle' });
  let newShift = $state('');
  let addingShift = $state(false);

  const els: Partial<Record<FormField, HTMLElement | undefined>> = $state({});

  const dirty = $derived(isDirty(initial, form));
  const version = $derived($bootstrap?.version ?? '');
  const rate = $derived(parsePayRate(form.pay_rate));
  const payHint = $derived(payPreview(rate, form.target_hours));
  const dv = $derived(dlcView($dlc));

  const appearanceOptions: { value: Appearance; label: string; icon: IconName }[] = [
    { value: 'System', label: 'System', icon: 'monitor' },
    { value: 'Light', label: 'Light', icon: 'sun' },
    { value: 'Dark', label: 'Dark', icon: 'moon' },
  ];
  const exportOptions: { value: ExportFormat; label: string; hint: string }[] = [
    { value: 'Simple', label: 'Simple', hint: 'Clean sheet: date, times and hours.' },
    { value: 'Full', label: 'Full', hint: 'The original detailed EAS timesheet layout.' },
  ];

  function setAppearance(a: Appearance) {
    form.appearance = a;
    appearancePreview.set(a === get(settings).appearance ? null : a);
  }

  function clearError(f: FormField) {
    if (errors[f]) errors = { ...errors, [f]: undefined };
  }

  async function save(): Promise<boolean> {
    if (saving) return false;
    saving = true;
    try {
      const r = await api.save_settings(draftFromForm(form, get(settings)));
      if (r.status === 'invalid') {
        const f = fieldOf(r.field);
        if (f) {
          errors = { [f]: r.message };
          (els[f]?.querySelector?.('input') ?? els[f])?.focus?.();
        } else {
          await reportError(r, 'Could not save settings');
        }
        return false;
      }
      if (!r.ok) {
        await reportError(r, 'Could not save settings');
        return false;
      }
      errors = {};
      applySettings(r.settings, r.shifts);
      appearancePreview.set(null);
      leaving = true;
      void refreshTimer();
      void refreshMonth();
      await navigate('main');
      toast(r.message ?? 'Settings saved.', { tone: 'success', ms: 2500 });
      return true;
    } finally {
      saving = false;
    }
  }

  async function back(): Promise<void> {
    if (saving || leaving) return;
    if (dirty) {
      const yes = await askYesNoCancel('Save changes?', 'You changed some settings.\n\nSave them before going back?');
      if (yes === null) return;
      if (yes) {
        await save();
        return;
      }
    }
    appearancePreview.set(null);
    leaving = true;
    await navigate('main');
  }

  async function checkNow() {
    if (check.kind === 'checking') return;
    check = { kind: 'checking' };
    const r = await api.check_updates();
    if (!r.ok) {
      check = {
        kind: 'error',
        message: r.status === 'error' ? r.error.message : (r.message ?? 'Could not check for updates.'),
      };
      return;
    }
    check = checkOutcome(r.app, r.dlc, version);
    if (r.dlc?.available && r.dlc.latest && $dlc.state !== 'missing') {
      dlc.update((d) => ({ ...d, update_version: r.dlc!.latest }));
    }
    if (check.kind === 'available') void promptUpdate(check.version, check.current, { wait: false });
  }

  async function addShift() {
    const name = newShift.trim();
    if (!name || addingShift) return;
    addingShift = true;
    try {
      const r = await api.add_job_shift(name);
      if (!r.ok) {
        await reportError(r, 'Could not add the shift');
        return;
      }
      shifts.set(r.shifts);
      if (!r.added) {
        await alert('Already exists', r.message ?? `'${name}' is already in the shift list.`, 'info');
        return;
      }
      newShift = '';
      form.default_job_shift = r.shifts.find((s) => s.toLowerCase() === name.toLowerCase()) ?? name;
      clearError('default_job_shift');
      toast(`Added '${name}' to your shifts.`, { tone: 'success', ms: 2500 });
    } finally {
      addingShift = false;
    }
  }

  async function openShiftsFile() {
    const r = await api.open_shifts_file();
    if (!r.ok) await reportError(r, 'Could not open shifts.txt');
  }

  async function toggleLulz(v: boolean) {
    await saveUiPrefs({ lulz: v });
  }
  async function toggleLulzSound(v: boolean) {
    // emitted after the save resolves; relies on the click's (sticky) user activation to unlock audio
    if ((await saveUiPrefs({ lulz_sound: v })) && v) emitFx({ kind: 'soundcheck' });
  }
  async function toggleReduce(v: boolean) {
    await saveUiPrefs({ reduce_effects: v });
  }

  const offs = [
    registerCommand('settings.save', () => void save()),
    registerCommand('settings.back', () => back()),
  ];
  onDestroy(() => {
    offs.forEach((f) => f());
    appearancePreview.set(null);
  });

  const lulz = $derived($settings.ui_prefs.lulz);
  const reduceFx = $derived($settings.ui_prefs.reduce_effects);
  const lulzBlocked = $derived(reduceFx || $prefersReducedMotion);
  const lulzSound = $derived($settings.ui_prefs.lulz_sound);
  const soundOff = $derived(!lulz || lulzBlocked);
  const checkedAgo = (at: number) => new Date(at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
</script>

<section class="settings" aria-labelledby="settings-title">
  <header class="top glass glass-strong" in:fly={{ y: -8 }}>
    <Button variant="ghost" icon="chevron-left" onclick={back} tooltip={{ text: 'Back', kbd: 'Esc' }}>Back</Button>
    <h2 id="settings-title">
      <span class="title-icon"><Icon name="settings" size={18} /></span>
      Settings
      {#if dirty}<span class="unsaved" in:fly={{ x: -6 }}>Unsaved changes</span>{/if}
    </h2>
    <Button variant="primary" glow icon="check" loading={saving} onclick={save} tooltip={{ text: 'Save', kbd: 'Ctrl+S' }}>
      Save
    </Button>
  </header>

  <div class="grid">
    <!-- About & updates -->
    <GlassCard tag="section" class="card" aria-labelledby="s-about" padding="20px" radius="lg">
      <div class="card-in" in:fly={{ y: 12, delay: stagger(0, 50) }}>
        <h3 id="s-about"><Icon name="sparkles" size={16} /> About & Updates</h3>
        <div class="about">
          <div class="brand">
            <span class="wizard" aria-hidden="true"><img src={wizard} alt="" width="512" height="512" /></span>
            <div>
              <div class="app-name">Työaikaweleho</div>
              <div class="muted mono small">v{version}</div>
            </div>
          </div>
          <Button
            variant="secondary"
            icon="refresh"
            loading={check.kind === 'checking'}
            onclick={checkNow}
          >
            {check.kind === 'checking' ? 'Checking…' : 'Check for updates'}
          </Button>
        </div>
        <div class="check-line" aria-live="polite">
          {#if check.kind === 'uptodate'}
            <p class="state ok" in:fly={{ y: 4 }}>
              <Icon name="success" size={15} /> You're up to date (v{check.version}).
              <span class="muted small">Checked {checkedAgo(check.at)}</span>
            </p>
            {#if check.dlcNote}<p class="state info small">{check.dlcNote}</p>{/if}
          {:else if check.kind === 'available'}
            <p class="state accent" in:fly={{ y: 4 }}>
              <Icon name="download" size={15} /> Version {check.version} is available.
              <button type="button" class="link" onclick={() => promptUpdate(check.kind === 'available' ? check.version : '', undefined, { wait: false })}>
                Install…
              </button>
            </p>
          {:else if check.kind === 'error'}
            <p class="state bad" in:fly={{ y: 4 }}><Icon name="error" size={15} /> {check.message}</p>
          {/if}
        </div>
      </div>
    </GlassCard>

    <!-- Appearance -->
    <GlassCard tag="section" class="card" aria-labelledby="s-look" padding="20px" radius="lg">
      <div class="card-in" in:fly={{ y: 12, delay: stagger(1, 50) }}>
        <h3 id="s-look"><Icon name="sun" size={16} /> Appearance</h3>
        <p class="muted small">Previewed live. Saved when you press Save.</p>
        <Segmented label="Appearance" value={form.appearance} options={appearanceOptions} onchange={setAppearance} />

        <div class="divider"></div>
        <h3 id="s-fx"><Icon name="flame" size={16} /> Effects</h3>
        <div class="switch-row">
          <div>
            <div class="row-title">Lulz <span aria-hidden="true">🔥</span></div>
            <div class="muted small">
              {#if lulzBlocked}
                Off while {reduceFx ? 'Reduce effects' : 'system reduced motion'} is on.
              {:else}
                Extra playful effects. Saved instantly.
              {/if}
            </div>
          </div>
          <Switch label="Lulz" checked={lulz && !lulzBlocked} disabled={lulzBlocked} onchange={toggleLulz} />
        </div>
        <div class="switch-row">
          <div>
            <div class="row-title">Lulz sound <span aria-hidden="true">🔊</span></div>
            <div class="muted small">
              {#if soundOff}
                Needs Lulz on.
              {:else}
                Synthesized crackle, whoosh and boom. Saved instantly.
              {/if}
            </div>
          </div>
          <Switch label="Lulz sound" checked={lulzSound && !soundOff} disabled={soundOff} onchange={toggleLulzSound} />
        </div>
        <div class="switch-row">
          <div>
            <div class="row-title">Reduce effects</div>
            <div class="muted small">Fewer animations and lighter visuals. Saved instantly.</div>
          </div>
          <Switch label="Reduce effects" checked={reduceFx} onchange={toggleReduce} />
        </div>
      </div>
    </GlassCard>

    <!-- Timer & pay -->
    <GlassCard tag="section" class="card" aria-labelledby="s-timer" padding="20px" radius="lg">
      <div class="card-in" in:fly={{ y: 12, delay: stagger(2, 50) }}>
        <h3 id="s-timer"><Icon name="clock" size={16} /> Timer & Pay</h3>

        <div bind:this={els.target_hours}>
          <Field label="Daily target" forId="set-target" error={errors.target_hours} hint="Fills the ring on the timer page.">
            <div class="slider-row">
              <input
                id="set-target"
                type="range"
                min={TARGET_MIN}
                max={TARGET_MAX}
                step={TARGET_STEP}
                bind:value={form.target_hours}
                oninput={() => {
                  form.target_hours = clampTarget(Number(form.target_hours));
                  clearError('target_hours');
                }}
                aria-describedby={describedBy('set-target')}
                aria-valuetext={formatTarget(form.target_hours)}
                style="--p: {((form.target_hours - TARGET_MIN) / (TARGET_MAX - TARGET_MIN)) * 100}%"
              />
              <span class="target-val num">{formatTarget(form.target_hours)}</span>
            </div>
          </Field>
        </div>

        <div class="two">
          <div bind:this={els.default_start_time}>
            <Field label="Default start time" forId="set-start" error={errors.default_start_time} hint="Preset for Start at…">
              <TimeInput
                id="set-start"
                bind:value={form.default_start_time}
                invalid={!!errors.default_start_time}
                describedby={describedBy('set-start')}
                onchange={() => clearError('default_start_time')}
              />
            </Field>
          </div>
          <div bind:this={els.pay_rate}>
            <Field label="Pay rate (€/hr)" forId="set-rate" error={errors.pay_rate} hint={payHint ?? 'e.g. 20 or 20,50'}>
              <TextInput
                id="set-rate"
                bind:value={form.pay_rate}
                inputmode="decimal"
                mono
                invalid={!!errors.pay_rate}
                aria-describedby={describedBy('set-rate')}
                oninput={() => clearError('pay_rate')}
              >
                {#snippet leading()}<span class="euro" aria-hidden="true">€</span>{/snippet}
              </TextInput>
            </Field>
          </div>
        </div>
      </div>
    </GlassCard>

    <!-- Job shifts -->
    <GlassCard tag="section" class="card" aria-labelledby="s-shift" padding="20px" radius="lg">
      <div class="card-in" in:fly={{ y: 12, delay: stagger(3, 50) }}>
        <h3 id="s-shift"><Icon name="list" size={16} /> Job shifts</h3>
        <div bind:this={els.default_job_shift}>
          <Field label="Default job shift" forId="set-job" error={errors.default_job_shift} hint="Preselected when starting the timer.">
            <Combobox
              id="set-job"
              bind:value={form.default_job_shift}
              options={$shifts}
              placeholder="None"
              invalid={!!errors.default_job_shift}
              describedby={describedBy('set-job')}
              onchange={() => clearError('default_job_shift')}
            />
          </Field>
        </div>
        <Field label="Add a shift" forId="set-newshift">
          <div class="add-row">
            <TextInput
              id="set-newshift"
              bind:value={newShift}
              placeholder="e.g. Night shift"
              onkeydown={(e: KeyboardEvent) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void addShift();
                }
              }}
            />
            <Button variant="secondary" icon="plus" loading={addingShift} disabled={!newShift.trim()} onclick={addShift}>Add</Button>
          </div>
        </Field>
        <div class="shift-foot">
          <span class="muted small">{$shifts.length} shift{$shifts.length === 1 ? '' : 's'} in your list</span>
          <Button variant="ghost" size="sm" icon="external" onclick={openShiftsFile}>Edit shifts.txt</Button>
        </div>
      </div>
    </GlassCard>

    <!-- Export -->
    <GlassCard tag="section" class="card" aria-labelledby="s-out" padding="20px" radius="lg">
      <div class="card-in" in:fly={{ y: 12, delay: stagger(4, 50) }}>
        <h3 id="s-out"><Icon name="download" size={16} /> Excel export</h3>
        <Segmented label="Export format" bind:value={form.export_format} options={exportOptions} />
        <p class="muted small">{exportOptions.find((o) => o.value === form.export_format)?.hint}</p>
        <div class="switch-row">
          <div>
            <div class="row-title">Include pay</div>
            <div class="muted small">Adds rate and earnings (€) rows to Simple exports.</div>
          </div>
          <Switch label="Include pay in export" bind:checked={form.export_include_pay} />
        </div>
      </div>
    </GlassCard>

    <!-- DLC store -->
    <GlassCard tag="section" class="card dlc" aria-labelledby="s-dlc" padding="20px" radius="lg">
      <div class="card-in" in:fly={{ y: 12, delay: stagger(5, 50) }}>
        <h3 id="s-dlc"><Icon name="puzzle" size={16} /> DLC Store</h3>
        <div class="dlc-item tone-{dv.tone}">
          <span class="dlc-icon" aria-hidden="true"><Icon name="image" size={22} /></span>
          <div class="dlc-body">
            <div class="dlc-head">
              <span class="row-title">{dv.headline}</span>
              <span class="badge">{dv.badge}</span>
            </div>
            <p class="muted small">Import timesheets from photos or screenshots with Windows built-in OCR.</p>
            {#if dv.detail}<p class="detail small">{dv.detail}</p>{/if}
            <div class="dlc-actions">
              {#if dv.primary}
                <Button
                  variant="primary"
                  glow
                  icon={dv.primary.action === 'install' ? 'download' : 'refresh'}
                  loading={$dlcBusy === dv.primary.action}
                  disabled={!!$dlcBusy}
                  onclick={() => dv.primary && installDlc(dv.primary.action)}
                >
                  {dv.primary.label}
                </Button>
              {/if}
              {#if dv.canRemove}
                <Button variant="ghost" icon="trash" loading={$dlcBusy === 'remove'} disabled={!!$dlcBusy} onclick={removeDlc}>
                  Remove
                </Button>
              {/if}
            </div>
          </div>
        </div>
      </div>
    </GlassCard>

    <!-- Shortcuts -->
    <GlassCard tag="section" class="card wide" aria-labelledby="s-keys" padding="20px" radius="lg">
      <div class="card-in" in:fly={{ y: 12, delay: stagger(6, 50) }}>
        <h3 id="s-keys"><Icon name="keyboard" size={16} /> Keyboard shortcuts</h3>
        <table class="keys">
          <tbody>
            {#each SHORTCUTS as s (s.what)}
              <tr>
                <td class="k">
                  {#each s.keys as k, i (k)}
                    {#if i}<span class="muted small"> / </span>{/if}
                    {#if k.startsWith('Click')}<span class="small">{k}</span>{:else}<Kbd keys={k} />{/if}
                  {/each}
                </td>
                <td>{s.what}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </GlassCard>
  </div>
</section>

<style>
  .settings {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 1080px;
    margin: 0 auto;
    padding: 4px 4px 32px;
  }
  .top {
    position: sticky;
    top: -4px; /* the scroll container's top padding */
    z-index: 5;
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: var(--radius-lg);
  }
  h2 {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: var(--fs-lg);
    font-weight: 700;
  }
  .title-icon {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border-radius: 10px;
    color: var(--on-accent);
    background: linear-gradient(135deg, var(--accent-strong), var(--accent-strong-2));
    box-shadow: 0 4px 16px var(--accent-glow);
  }
  .unsaved {
    padding: 2px 9px;
    border-radius: var(--radius-pill);
    font-size: var(--fs-xs);
    font-weight: 650;
    color: var(--warning-text);
    background: color-mix(in srgb, var(--amber) 16%, transparent);
  }
  /* Masonry columns: cards of different heights pack without row gaps. */
  .grid {
    columns: 340px;
    column-gap: 16px;
  }
  .grid > :global(.card) {
    break-inside: avoid;
    margin-bottom: 16px;
  }
  .grid :global(.card.wide) {
    column-span: all;
  }
  .card-in {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  h3 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: var(--fs-md);
    font-weight: 700;
    color: var(--text);
  }
  h3 :global(svg) {
    color: var(--accent-text);
  }
  .small {
    font-size: var(--fs-sm);
  }
  .divider {
    height: 1px;
    background: var(--divider);
    margin: 4px 0;
  }
  .about {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  /* top of the splash art (bubble + wizard), framed like the glass cards */
  .wizard {
    display: block;
    flex: none;
    width: 104px;
    aspect-ratio: 1 / 0.68;
    overflow: hidden;
    border-radius: var(--radius-md);
    border: 1px solid var(--glass-border);
    box-shadow: inset 0 1px 0 var(--glass-highlight), 0 6px 24px var(--accent-glow);
  }
  .wizard img {
    display: block;
    width: 100%;
    height: auto;
  }
  .app-name {
    font-weight: 700;
  }
  .check-line:empty {
    display: none;
  }
  .state {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
  }
  .state.ok {
    color: var(--success-text);
  }
  .state.info {
    color: var(--info-text);
  }
  .state.accent {
    color: var(--accent-text);
  }
  .state.bad {
    color: var(--danger-text);
  }
  .link {
    border: 0;
    padding: 0;
    background: none;
    font: inherit;
    font-weight: 650;
    color: var(--accent-text);
    text-decoration: underline;
    cursor: pointer;
  }
  .switch-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 8px 0;
  }
  .row-title {
    font-weight: 650;
  }
  .two {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 12px;
  }
  .slider-row {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .target-val {
    min-width: 92px;
    text-align: right;
    font-weight: 650;
  }
  input[type='range'] {
    flex: 1;
    height: 6px;
    border-radius: var(--radius-pill);
    appearance: none;
    background: linear-gradient(
      90deg,
      var(--accent-strong) 0,
      var(--accent-strong-2) var(--p),
      var(--neutral-fill) var(--p)
    );
    cursor: pointer;
  }
  input[type='range']::-webkit-slider-thumb {
    appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #fff;
    box-shadow:
      0 0 0 3px var(--accent),
      0 2px 10px var(--accent-glow);
    transition: transform var(--dur-fast) var(--ease-spring);
  }
  input[type='range']:active::-webkit-slider-thumb {
    transform: scale(1.15);
  }
  input[type='range']:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 4px;
  }
  .euro {
    color: var(--text-muted);
    font-weight: 650;
  }
  .add-row {
    display: flex;
    gap: 8px;
  }
  .add-row :global(.text-input),
  .add-row > :global(:first-child) {
    flex: 1;
    min-width: 0;
  }
  .add-row :global(input) {
    min-width: 0;
  }
  .shift-foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .dlc-item {
    display: flex;
    gap: 14px;
  }
  .dlc-icon {
    flex: none;
    display: grid;
    place-items: center;
    width: 48px;
    height: 48px;
    border-radius: 14px;
    color: var(--info-text);
    background: color-mix(in srgb, var(--cyan) 14%, transparent);
  }
  .dlc-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .dlc-head {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
  }
  .badge {
    padding: 2px 9px;
    border-radius: var(--radius-pill);
    font-size: var(--fs-xs);
    font-weight: 650;
    color: var(--text-muted);
    background: var(--neutral-fill);
  }
  .tone-ok .badge {
    color: var(--success-text);
    background: color-mix(in srgb, var(--success-text) 14%, transparent);
  }
  .tone-update .badge {
    color: var(--accent-text);
    background: color-mix(in srgb, var(--accent) 16%, transparent);
  }
  .tone-warning .badge,
  .tone-warning .detail {
    color: var(--warning-text);
  }
  .tone-warning .badge {
    background: color-mix(in srgb, var(--amber) 16%, transparent);
  }
  .dlc-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 4px;
  }
  .keys {
    width: 100%;
    border-collapse: collapse;
  }
  .keys td {
    padding: 7px 4px;
    border-bottom: 1px solid var(--divider);
  }
  .keys tr:last-child td {
    border-bottom: 0;
  }
  .keys .k {
    width: 40%;
    white-space: nowrap;
  }
</style>

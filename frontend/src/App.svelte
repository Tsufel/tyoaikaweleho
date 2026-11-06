<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { readable } from 'svelte/store';
  import logo from './assets/logo.webp';
  import Intro from './fx/Intro.svelte';
  import MeshBackground from './fx/MeshBackground.svelte';
  import { api, onEvent } from './lib/api';
  import type { ChangelogBlock, RecoveryResult } from './lib/api/types';
  import { fade, fly } from './lib/motion';
  import { registerCommand, runCommand, SHORTCUT_LABELS } from './lib/shortcuts';
  import { animationsActive, bootstrap, lulz, modalOpen, motion, navigate, route, section, type Section } from './lib/stores/app';
  import { goToCurrentMonth, refreshMonth, setViewMonth, shiftMonth, viewMonth } from './lib/stores/entries';
  import { applyRecoveryResult, notifyDataRecovery, pendingRecovery } from './lib/stores/recovery';
  import { glassMode, startGlass } from './lib/stores/glass';
  import LiquidFilters from './lib/glass/LiquidFilters.svelte';
  import { liquidGlass } from './lib/glass/liquidGlass';
  import { applySettings, dlc, saveUiPrefs, settings } from './lib/stores/settings';
  import { setTimer, timer } from './lib/stores/timer';
  import { runUndo, toast } from './lib/stores/toasts';
  import { startTheme } from './lib/theme/theme';
  import { MONTHS, monthLabel } from './lib/time';
  import { applyZoom, cleanZoom, stepZoom, ZOOM_DEFAULT } from './lib/zoom';
  import { startFocusRefresh } from './lib/focusRefresh';
  import { tooltip } from './lib/ui/actions';
  import Button from './lib/ui/Button.svelte';
  import ConfirmHost from './lib/ui/ConfirmHost.svelte';
  import Icon from './lib/ui/Icon.svelte';
  import MonthGrid from './lib/ui/MonthGrid.svelte';
  import Popover from './lib/ui/Popover.svelte';
  import Segmented from './lib/ui/Segmented.svelte';
  import Spinner from './lib/ui/Spinner.svelte';
  import Toasts from './lib/ui/Toasts.svelte';
  import { onShift, startAchievements } from './lib/stores/achievements';
  import AchievementUnlock from './views/achievements/AchievementUnlock.svelte';
  import PetFlyby from './views/pet/PetFlyby.svelte';
  import WeeklyRecap from './views/recap/WeeklyRecap.svelte';
  import { petFlyby } from './views/pet/petState';
  import ChangelogModal from './views/modals/ChangelogModal.svelte';
  import { handleCloseRequest } from './views/modals/closeFlow';
  import RecoverShiftModal from './views/modals/RecoverShiftModal.svelte';
  import ShortcutsModal from './views/modals/ShortcutsModal.svelte';
  import CommandPalette from './views/modals/CommandPalette.svelte';
  import { emitFx } from './fx/fire/fxBus';
  import { rollBazooka } from './views/pet/petState';
  import EntriesView from './views/entries/EntriesView.svelte';
  import SettingsView from './views/settings/SettingsView.svelte';
  import UpdateFlow from './views/settings/UpdateFlow.svelte';
  import TimerView from './views/timer/TimerView.svelte';

  type Phase = 'loading' | 'error' | 'ready';
  let phase = $state<Phase>('loading');
  let loadError = $state('');
  let introDone = $state(false);
  /** The window is shown: start the intro timeline. */
  let introPlay = $state(false);
  let segReset = $state(0);
  let changelog = $state<ChangelogBlock[] | null>(null);
  let monthBtn = $state<HTMLButtonElement>();
  let monthOpen = $state(false);
  let winWidth = $state(window.innerWidth);
  let shortcutsOpen = $state(false);
  let paletteOpen = $state(false);
  /** "Zoom 110 %" shown briefly after a zoom key. */
  let zoomMsg = $state('');
  let zoomMsgTimer: ReturnType<typeof setTimeout> | undefined;
  // Bumped by Retry when a lazy chunk failed to load.
  let statsTry = $state(0);
  let contentEl = $state<HTMLElement>();
  let routeMsg = $state('');
  /** Log a failed chunk import once per kind (a broken install, a locked file). */
  const chunkLogged = new Set<string>();
  function chunkFailed(what: string, err: unknown): string {
    const msg = err instanceof Error ? err.message : String(err);
    if (!chunkLogged.has(what)) {
      chunkLogged.add(what);
      void api.log_client_error(`Could not load the ${what} chunk: ${msg}`.slice(0, 2000));
    }
    return msg;
  }
  const loadStats = () => import('./views/stats/StatsView.svelte');
  // Lulz overlay, sound and milestones: lazy so the fx chunk only loads with Lulz on.
  const loadFx = () =>
    import('./fx/fire/FxDirector.svelte').catch((err) => {
      chunkFailed('effects', err); // the effects are extras: carry on without them
      return null;
    });

  /** The Konami code: a little show, nothing saved. */
  function wizardSecret() {
    toast('🧙 The wizard approves of your hours.', { tone: 'success', ms: 5000 });
    if ($lulz && $motion !== 'reduced') emitFx({ kind: 'blast', minutes: null });
    if ($settings.ui_prefs.pet !== 'off') rollBazooka(0);
  }

  const zoom = $derived(cleanZoom($settings.ui_prefs.zoom));

  function setZoom(z: number) {
    zoomMsg = `Zoom ${z} %`;
    clearTimeout(zoomMsgTimer);
    zoomMsgTimer = setTimeout(() => (zoomMsg = ''), 1500);
    if (z !== zoom) void saveUiPrefs({ zoom: z });
  }

  // App-level fallbacks, registered before child views so theirs win.
  const offs = [
    registerCommand('settings.open', () => void navigate('settings')),
    registerCommand('undo', () => void runUndo()),
    registerCommand('month.prev', () => void shiftMonth(-1)),
    registerCommand('month.next', () => void shiftMonth(1)),
    registerCommand('month.current', () => void goToCurrentMonth()),
    // shell shortcuts: views, the cheat sheet and one secret
    registerCommand('view.timer', () => void pickSection('timer')),
    registerCommand('view.shifts', () => void pickSection('shifts')),
    registerCommand('view.stats', () => void pickSection('stats')),
    registerCommand('stats.back', () => void navigate('main')),
    registerCommand('help.shortcuts', () => {
      shortcutsOpen = true;
    }),
    registerCommand('wizard.secret', wizardSecret),
    registerCommand('zoom.in', () => setZoom(stepZoom(zoom, 1))),
    registerCommand('zoom.out', () => setZoom(stepZoom(zoom, -1))),
    registerCommand('zoom.reset', () => setZoom(ZOOM_DEFAULT)),
    registerCommand('palette.open', () => {
      paletteOpen = true;
    }),
  ];
  onDestroy(() => {
    offs.forEach((f) => f());
    clearTimeout(zoomMsgTimer);
  });

  const sections: { value: Section; label: string; icon: 'timer' | 'list' | 'chart' }[] = [
    { value: 'timer', label: 'Timer', icon: 'timer' },
    { value: 'shifts', label: 'Shifts', icon: 'list' },
    { value: 'stats', label: 'Stats', icon: 'chart' },
  ];

  async function pickSection(v: Section) {
    if (v === 'stats') {
      if (!(await navigate('stats'))) {
        section.set($route === 'stats' ? 'stats' : 'timer');
        segReset++; // Segmented already shows 'stats'
        await tick();
        // the remount dropped the focused radio
        if (focusLost()) document.querySelector<HTMLElement>('.topbar [role="radio"][aria-checked="true"]')?.focus();
      }
      return;
    }
    if (!(await navigate('main'))) return;
    section.set(v);
    await tick();
    document.getElementById(v === 'timer' ? 'pane-timer' : 'pane-shifts')?.scrollIntoView({ block: 'nearest' });
  }

  async function load() {
    phase = 'loading';
    const r = await api.bootstrap();
    if (!r.ok) {
      loadError = r.message ?? (r.status === 'error' ? r.error.message : 'Could not load data.');
      phase = 'error';
      return;
    }
    const b = r.data;
    bootstrap.set(b);
    applySettings(b.settings, b.shifts);
    setTimer(b.timer);
    dlc.set(b.dlc);
    viewMonth.set(b.month);
    void refreshMonth();
    changelog = b.changelog?.length ? b.changelog : null;
    // §6.3: offered after the changelog; START stays blocked until resolved.
    pendingRecovery.set(b.recovery);
    notifyDataRecovery(b.data_recovery);
    phase = 'ready';
  }

  async function onRecoveryResolved(r: RecoveryResult) {
    await applyRecoveryResult(r);
  }

  const focusLost = () => !document.activeElement || document.activeElement === document.body;

  // Route change: say where we are, and catch focus the old page took with it.
  const ROUTE_NAMES = { main: 'Timer and shifts', stats: 'Stats', settings: 'Settings' } as const;
  let lastRoute = $route;
  $effect(() => {
    const r = $route;
    if (r === lastRoute) return;
    lastRoute = r;
    routeMsg = ROUTE_NAMES[r] ?? '';
    void tick().then(() => {
      if (!focusLost()) return;
      const heading = contentEl?.querySelector<HTMLElement>('[data-route-heading]');
      (heading ?? contentEl)?.focus({ preventScroll: true });
    });
  });

  // the UI zoom (ui_prefs.zoom) on <html>
  $effect(() => applyZoom(zoom));

  // html[data-motion], html[data-paused]
  $effect(() => {
    document.documentElement.dataset.motion = $motion;
  });
  $effect(() => {
    document.documentElement.dataset.paused = String(!$animationsActive);
  });
  // after the intro, so the backfill toast / first unlock isn't hidden under it
  $effect(() => {
    if (phase === 'ready' && introDone) startAchievements();
  });

  onMount(() => {
    const stopTheme = startTheme(readable(true));
    // html[data-glass] / html[data-refract]: absent while Liquid glass is off
    const stopGlass = startGlass();
    const offClose = onEvent('close:requested', () => void handleCloseRequest());
    const offActivate = onEvent('app:activate', () => window.focus());
    // load() failed and Python's watchdog showed the window anyway
    const introFallback = setTimeout(() => (introPlay = true), 7000);
    const onResize = () => (winWidth = window.innerWidth);
    window.addEventListener('resize', onResize);
    // edits another process made show up when the window comes back
    const stopFocusRefresh = startFocusRefresh();

    void (async () => {
      await load();
      void api.set_close_guard(true);
      await document.fonts?.ready;
      // The native window starts hidden, and hidden WebView2 pages get no
      // animation frames, so don't wait on rAF alone.
      let told = false;
      const tell = () => {
        if (told) return;
        told = true;
        void api.frontend_ready().finally(() => (introPlay = true));
      };
      requestAnimationFrame(() => requestAnimationFrame(tell));
      setTimeout(tell, 120);
    })();

    return () => {
      stopTheme();
      stopGlass();
      offClose();
      offActivate();
      clearTimeout(introFallback);
      window.removeEventListener('resize', onResize);
      stopFocusRefresh();
    };
  });

  // two panes side by side from 1080 layout px (the zoom makes fewer fit)
  const wide = $derived(winWidth * (100 / zoom) >= 1080);
  const showTimer = $derived($route === 'main' && (wide || $section === 'timer'));
  const showShifts = $derived($route === 'main' && (wide || $section === 'shifts'));
  const segValue = $derived<Section>($route === 'stats' ? 'stats' : $section);
</script>

<MeshBackground />
{#if $glassMode === 'refract'}
  <LiquidFilters />
{/if}

<div class="shell" data-fx-root inert={$modalOpen > 0 || !introDone}>
  <header class="topbar glass lg-float" use:liquidGlass={'topbar'}>
    <div class="brand">
      <img src={logo} alt="" width="28" height="28" />
      <span class="name">Työaikaweleho</span>
    </div>

    <div class="center">
      {#if $route !== 'settings'}
        {#key segReset}
          <Segmented value={segValue} options={sections} label="View" onchange={pickSection} />
        {/key}
      {/if}
    </div>

    <div class="right">
      {#if $route === 'main'}
        <div class="month-nav" role="group" aria-label="Month">
          <button type="button" class="nav lg-gel" aria-label="Previous month" use:tooltip={{ text: 'Previous month', kbd: SHORTCUT_LABELS['month.prev'] }} onclick={() => shiftMonth(-1)}>
            <Icon name="chevron-left" size={16} />
          </button>
          <button
            bind:this={monthBtn}
            type="button"
            class="month lg-gel"
            aria-haspopup="dialog"
            aria-expanded={monthOpen}
            onclick={() => (monthOpen = !monthOpen)}
          >
            {monthLabel($viewMonth.year, $viewMonth.month)}
          </button>
          <button type="button" class="nav lg-gel" aria-label="Next month" use:tooltip={{ text: 'Next month', kbd: SHORTCUT_LABELS['month.next'] }} onclick={() => shiftMonth(1)}>
            <Icon name="chevron-right" size={16} />
          </button>
        </div>
      {/if}
      <Button
        variant="ghost"
        square
        icon="keyboard"
        label="Keyboard shortcuts"
        tooltip={{ text: 'Keyboard shortcuts', kbd: SHORTCUT_LABELS['help.shortcuts'] }}
        onclick={() => (shortcutsOpen = true)}
      />
      <Button
        variant={$route === 'settings' ? 'primary' : 'ghost'}
        square
        icon="settings"
        label="Settings"
        tooltip={{ text: 'Settings', kbd: SHORTCUT_LABELS['settings.open'] }}
        aria-pressed={$route === 'settings'}
        onclick={() => {
          // settings.back asks about unsaved changes before leaving
          if ($route !== 'settings') void navigate('settings');
          else if (!runCommand('settings.back')) void navigate('main');
        }}
      />
    </div>
  </header>

  <main class="content" tabindex="-1" bind:this={contentEl}>
    {#if phase === 'loading'}
      <div class="center-state" in:fade><Spinner size={28} label="Loading" /></div>
    {:else if phase === 'error'}
      <div class="center-state glass" role="alert" in:fade>
        <Icon name="error" size={28} />
        <p>{loadError}</p>
        <Button variant="primary" icon="refresh" onclick={load}>Try again</Button>
      </div>
    {:else if $route === 'settings'}
      <div class="page" in:fly={{ y: 10 }}><SettingsView /></div>
    {:else if $route === 'stats'}
      <div class="page" in:fly={{ y: 10 }}>
        {#key statsTry}
          {#await loadStats()}
            <div class="center-state"><Spinner size={28} label="Loading stats" /></div>
          {:then m}
            <m.default />
          {:catch err}
            <div class="center-state glass" role="alert">
              <Icon name="error" size={28} />
              <p>Could not load Stats. {chunkFailed('Stats', err)}</p>
              <Button variant="primary" icon="refresh" onclick={() => statsTry++}>Try again</Button>
            </div>
          {/await}
        {/key}
      </div>
    {:else}
      <div class="main-grid" class:wide>
        <!-- TimerView stays mounted on the main route so the running clock is never torn down -->
        <div id="pane-timer" class="pane" class:hidden={!showTimer}><TimerView /></div>
        {#if showShifts}
          <div id="pane-shifts" class="pane shifts" in:fly={{ y: 10 }}><EntriesView /></div>
        {/if}
      </div>
    {/if}
  </main>
</div>

{#if monthOpen}
  <Popover anchor={monthBtn} onclose={() => (monthOpen = false)} label="Choose month" placement="bottom-end">
    <MonthGrid
      year={$viewMonth.year}
      month={$viewMonth.month}
      onpick={(y, m) => {
        monthOpen = false;
        monthBtn?.focus();
        void setViewMonth(y, m);
      }}
    />
  </Popover>
{/if}

{#if phase === 'ready' && introDone}
  {#if changelog}
    <ChangelogModal blocks={changelog} onclose={() => (changelog = null)} />
  {:else if $pendingRecovery}
    {#key $pendingRecovery}
      <RecoverShiftModal recovery={$pendingRecovery} onresolved={onRecoveryResolved} />
    {/key}
  {/if}
{/if}

<UpdateFlow />
<ConfirmHost />
{#if phase === 'ready' && introDone}
  {#if $settings.ui_prefs.pet !== 'off'}<PetFlyby />{/if}
  <AchievementUnlock held={$modalOpen > 0} waiting={onShift($timer) || !!$petFlyby} />
  <WeeklyRecap held={$modalOpen > 0} waiting={onShift($timer) || !!$petFlyby} />
{/if}
<Toasts />
{#if $lulz}
  {#await loadFx() then m}
    {#if m}<m.default />{/if}
  {/await}
{/if}

{#if !introDone}
  <Intro version={$bootstrap?.version ?? ''} play={introPlay} ondone={() => (introDone = true)} />
{/if}

<span class="sr-only" aria-live="polite">{$route === 'main' ? `${MONTHS[$viewMonth.month - 1]} ${$viewMonth.year}` : ''}</span>
<span class="sr-only" aria-live="polite">{routeMsg}</span>

{#if shortcutsOpen}
  <ShortcutsModal onclose={() => (shortcutsOpen = false)} />
{/if}
{#if paletteOpen}
  <CommandPalette onclose={() => (paletteOpen = false)} />
{/if}
{#if zoomMsg}
  <div class="zoom-badge glass" role="status" transition:fade={{ duration: 120 }}>{zoomMsg}</div>
{/if}

<style>
  .shell {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    height: 100vh;
    padding: 12px 16px 16px;
    gap: 14px;
  }
  .topbar {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    gap: 12px;
    height: 56px;
    padding: 0 10px 0 14px;
    border-radius: var(--radius-lg);
    flex: none;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }
  .brand img {
    border-radius: 8px;
    flex: none;
  }
  .name {
    font-weight: 750;
    letter-spacing: -0.01em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .center {
    display: flex;
    justify-content: center;
  }
  .right {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
  }
  .month-nav {
    display: flex;
    align-items: center;
    gap: 2px;
    padding: 3px;
    border-radius: var(--radius-pill);
    background: var(--neutral-fill);
  }
  .nav,
  .month {
    height: 30px;
    border: 0;
    border-radius: var(--radius-pill);
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
    transition:
      background-color var(--dur-fast),
      color var(--dur-fast);
  }
  .nav {
    display: grid;
    place-items: center;
    width: 30px;
  }
  .month {
    min-width: 128px;
    white-space: nowrap;
    padding: 0 10px;
    color: var(--text);
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }
  .nav:hover,
  .month:hover,
  .month[aria-expanded='true'] {
    background: var(--neutral-fill-hover);
    color: var(--text);
  }
  /* Liquid glass: capsule topbar, clear chip group, gel press */
  :global(:root[data-glass='liquid']) .topbar {
    border-radius: 28px;
  }
  :global(:root[data-glass='liquid']) .month-nav {
    background: linear-gradient(180deg, var(--lg-sheen), transparent 60%), var(--lg-clear);
    box-shadow: inset 0 1px 0 var(--glass-highlight);
  }
  :global(:root[data-glass='liquid']:not([data-motion='reduced'])) .lg-gel {
    transition:
      background-color var(--dur-fast),
      color var(--dur-fast),
      scale 460ms var(--lg-spring);
  }
  :global(:root[data-glass='liquid']:not([data-motion='reduced'])) .lg-gel:active {
    scale: 1.06 0.94;
    transition-duration: var(--dur-fast), var(--dur-fast), 90ms;
  }
  .content {
    outline: none;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  /* Scroll containers clip their children's shadows: pad them and pull the
     padding back out so cards keep their place. */
  .page,
  .pane {
    padding: 4px 6px 16px;
    margin: -4px -6px -16px;
  }
  .page {
    flex: 1;
    min-height: 0;
    overflow: auto;
  }
  .main-grid {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 1fr;
    gap: 14px;
  }
  .main-grid.wide {
    grid-template-columns: minmax(340px, 5fr) 7fr;
  }
  .pane {
    min-width: 0;
    min-height: 0;
    overflow: auto;
    display: flex;
    flex-direction: column;
  }
  .pane > :global(*) {
    flex: 1;
  }
  .pane.hidden {
    display: none;
  }
  .center-state {
    margin: auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
    padding: 28px 32px;
    max-width: 420px;
    text-align: center;
    color: var(--text-muted);
  }
  .zoom-badge {
    position: fixed;
    top: 76px;
    left: 50%;
    translate: -50% 0;
    z-index: 200;
    padding: 6px 14px;
    border-radius: var(--radius-pill);
    font-weight: 650;
    font-variant-numeric: tabular-nums;
    pointer-events: none;
  }
  @media (max-width: 900px) {
    .name {
      display: none;
    }
    .shell {
      padding: 10px 12px 12px;
    }
  }
</style>

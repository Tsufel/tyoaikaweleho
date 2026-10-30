<script lang="ts">
  import { onDestroy, onMount, tick } from 'svelte';
  import { readable } from 'svelte/store';
  import logo from './assets/logo.webp';
  import Intro from './fx/Intro.svelte';
  import MeshBackground from './fx/MeshBackground.svelte';
  import { api, onEvent } from './lib/api';
  import type { ChangelogBlock, RecoveryResult } from './lib/api/types';
  import { fade, fly } from './lib/motion';
  import { registerCommand, runCommand } from './lib/shortcuts';
  import { animationsActive, bootstrap, lulz, modalOpen, motion, navigate, route, section, type Section } from './lib/stores/app';
  import { goToCurrentMonth, refreshMonth, setViewMonth, shiftMonth, viewMonth } from './lib/stores/entries';
  import { applyRecoveryResult, pendingRecovery } from './lib/stores/recovery';
  import { applySettings, dlc } from './lib/stores/settings';
  import { setTimer } from './lib/stores/timer';
  import { runUndo } from './lib/stores/toasts';
  import { startTheme } from './lib/theme/theme';
  import { MONTHS, monthLabel } from './lib/time';
  import { tooltip } from './lib/ui/actions';
  import Button from './lib/ui/Button.svelte';
  import ConfirmHost from './lib/ui/ConfirmHost.svelte';
  import Icon from './lib/ui/Icon.svelte';
  import MonthGrid from './lib/ui/MonthGrid.svelte';
  import Popover from './lib/ui/Popover.svelte';
  import Segmented from './lib/ui/Segmented.svelte';
  import Spinner from './lib/ui/Spinner.svelte';
  import Toasts from './lib/ui/Toasts.svelte';
  import ChangelogModal from './views/modals/ChangelogModal.svelte';
  import { handleCloseRequest } from './views/modals/closeFlow';
  import RecoverShiftModal from './views/modals/RecoverShiftModal.svelte';
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
  let wide = $state(true);
  const loadStats = () => import('./views/stats/StatsView.svelte');
  // Lulz overlay, sound and milestones: lazy so the fx chunk only loads with Lulz on.
  const loadFx = () => import('./fx/fire/FxDirector.svelte');

  // App-level fallbacks, registered before child views so theirs win.
  const offs = [
    registerCommand('settings.open', () => void navigate('settings')),
    registerCommand('undo', () => void runUndo()),
    registerCommand('month.prev', () => void shiftMonth(-1)),
    registerCommand('month.next', () => void shiftMonth(1)),
    registerCommand('month.current', () => void goToCurrentMonth()),
  ];
  onDestroy(() => offs.forEach((f) => f()));

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
    phase = 'ready';
  }

  async function onRecoveryResolved(r: RecoveryResult) {
    await applyRecoveryResult(r);
  }

  // html[data-motion], html[data-paused]
  $effect(() => {
    document.documentElement.dataset.motion = $motion;
  });
  $effect(() => {
    document.documentElement.dataset.paused = String(!$animationsActive);
  });

  onMount(() => {
    const stopTheme = startTheme(readable(true));
    const offClose = onEvent('close:requested', () => void handleCloseRequest());
    const offActivate = onEvent('app:activate', () => window.focus());
    // load() failed and Python's watchdog showed the window anyway
    const introFallback = setTimeout(() => (introPlay = true), 7000);
    const mq = window.matchMedia('(min-width: 1080px)');
    const onMq = () => (wide = mq.matches);
    onMq();
    mq.addEventListener('change', onMq);

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
      offClose();
      offActivate();
      clearTimeout(introFallback);
      mq.removeEventListener('change', onMq);
    };
  });

  const showTimer = $derived($route === 'main' && (wide || $section === 'timer'));
  const showShifts = $derived($route === 'main' && (wide || $section === 'shifts'));
  const segValue = $derived<Section>($route === 'stats' ? 'stats' : $section);
</script>

<MeshBackground />

<div class="shell" data-fx-root inert={$modalOpen > 0 || !introDone}>
  <header class="topbar glass">
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
          <button type="button" class="nav" aria-label="Previous month" use:tooltip={{ text: 'Previous month', kbd: 'PgUp' }} onclick={() => shiftMonth(-1)}>
            <Icon name="chevron-left" size={16} />
          </button>
          <button
            bind:this={monthBtn}
            type="button"
            class="month"
            aria-haspopup="dialog"
            aria-expanded={monthOpen}
            onclick={() => (monthOpen = !monthOpen)}
          >
            {monthLabel($viewMonth.year, $viewMonth.month)}
          </button>
          <button type="button" class="nav" aria-label="Next month" use:tooltip={{ text: 'Next month', kbd: 'PgDn' }} onclick={() => shiftMonth(1)}>
            <Icon name="chevron-right" size={16} />
          </button>
        </div>
      {/if}
      <Button
        variant={$route === 'settings' ? 'primary' : 'ghost'}
        square
        icon="settings"
        label="Settings"
        tooltip={{ text: 'Settings', kbd: 'Ctrl+,' }}
        aria-pressed={$route === 'settings'}
        onclick={() => {
          // settings.back asks about unsaved changes before leaving
          if ($route !== 'settings') void navigate('settings');
          else if (!runCommand('settings.back')) void navigate('main');
        }}
      />
    </div>
  </header>

  <main class="content">
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
        {#await loadStats()}
          <div class="center-state"><Spinner size={28} label="Loading stats" /></div>
        {:then m}
          <m.default />
        {/await}
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
<Toasts />
{#if $lulz}
  {#await loadFx() then m}
    <m.default />
  {/await}
{/if}

{#if !introDone}
  <Intro version={$bootstrap?.version ?? ''} play={introPlay} ondone={() => (introDone = true)} />
{/if}

<span class="sr-only" aria-live="polite">{$route === 'main' ? `${MONTHS[$viewMonth.month - 1]} ${$viewMonth.year}` : ''}</span>

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
  .content {
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
  @media (max-width: 900px) {
    .name {
      display: none;
    }
    .shell {
      padding: 10px 12px 12px;
    }
  }
</style>

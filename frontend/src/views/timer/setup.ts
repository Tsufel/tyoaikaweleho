import type { Component } from 'svelte';
import { registerCommand } from '../../lib/shortcuts';
import { registerConfirmRenderer, type ConfirmRendererProps } from '../../lib/stores/confirm';
import CloseModal from '../modals/CloseModal.svelte';
import StopConfirm, { type StopKind } from '../modals/StopConfirm.svelte';
import StartAheadConfirm from './StartAheadConfirm.svelte';
import { toggleTimer } from './timerActions';

// Imported by TimerView and closeFlow so the renderers and F5 exist on every
// route (TimerView is not mounted on stats/settings).
let installed = false;

export function installTimer(): void {
  if (installed) return;
  installed = true;
  const kinds: StopKind[] = ['stop_shift', 'long_shift', 'over_24h', 'discard_shift'];
  for (const kind of kinds) {
    registerConfirmRenderer(kind, StopConfirm as unknown as Component<ConfirmRendererProps<typeof kind>>);
  }
  registerConfirmRenderer('start_ahead', StartAheadConfirm);
  registerConfirmRenderer('close_running', CloseModal);
  registerCommand('timer.toggle', () => void toggleTimer());
}

installTimer();

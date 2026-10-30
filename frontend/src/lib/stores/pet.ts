import { get, writable } from 'svelte/store';
import { api } from '../api/bridge';
import type { PetStats } from '../api/types';
import { month } from './entries';
import { timer as timerState } from './timer';

// The pet's numbers come from get_pet_stats; like achievements they are
// re-read whenever the viewed month is (every save/edit/delete/import ends in
// refreshMonth). The target only matters to petLogic, so changing it needs no
// re-read. Only while a pet is shown (watchPetStats), so a user with the pet
// off never pays for it.

export const petStats = writable<PetStats | null>(null);

const REFRESH_DELAY_MS = 350;
let watchers = 0;
let stop: (() => void) | null = null;
let timer: ReturnType<typeof setTimeout> | undefined;
let running = false;
let again = false;

/** Ask Python now (coalesced). Failures are quiet and keep the last numbers. */
export async function refreshPetStats(): Promise<void> {
  if (running) {
    again = true;
    return;
  }
  running = true;
  try {
    do {
      again = false;
      try {
        const r = await api.get_pet_stats();
        if (r?.ok) petStats.set({ lifetime_minutes: r.lifetime_minutes, days: r.days });
      } catch {
        // keep the last numbers
      }
    } while (again);
  } finally {
    running = false;
  }
}

function schedule() {
  clearTimeout(timer);
  timer = setTimeout(() => void refreshPetStats(), REFRESH_DELAY_MS);
}

/** Keep petStats fresh while the returned cleanup hasn't been called. */
export function watchPetStats(): () => void {
  if (watchers++ === 0) {
    const offMonth = month.subscribe(() => schedule());
    // a stop saves (or discards) before the timer says so; re-read either way
    let wasRunning = get(timerState).running;
    const offTimer = timerState.subscribe((t) => {
      if (wasRunning && !t.running) schedule();
      wasRunning = t.running;
    });
    stop = () => {
      offMonth();
      offTimer();
      clearTimeout(timer);
    };
  }
  let done = false;
  return () => {
    if (done) return;
    done = true;
    if (--watchers === 0) {
      stop?.();
      stop = null;
    }
  };
}

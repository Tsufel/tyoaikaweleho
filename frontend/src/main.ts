import '@fontsource-variable/inter';
import '@fontsource-variable/jetbrains-mono';
import './lib/theme/tokens.css';
import './lib/theme/global.css';
import './lib/theme/liquid.css';
import { mount } from 'svelte';
import App from './App.svelte';
import { api } from './lib/api';
import { harden } from './lib/platform/harden';
import { startShortcuts } from './lib/shortcuts';

let reported = 0;
function report(message: string, stack?: string) {
  if (++reported > 20) return;
  void api.log_client_error(message.slice(0, 2000), stack?.slice(0, 8000));
}

window.addEventListener('error', (e) => report(String(e.message || e.error), e.error?.stack));
window.addEventListener('unhandledrejection', (e) => {
  const r = e.reason;
  report(`Unhandled rejection: ${r?.message ?? String(r)}`, r?.stack);
});

harden();
startShortcuts();

const app = mount(App, { target: document.getElementById('app')! });
document.getElementById('boot')?.remove();

export default app;

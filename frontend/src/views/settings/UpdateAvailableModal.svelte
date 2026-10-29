<script lang="ts">
  import Button from '../../lib/ui/Button.svelte';
  import Icon from '../../lib/ui/Icon.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  let { version, current, onclose }: { version: string; current: string; onclose: (install: boolean) => void } = $props();
  const descId = `upd-${Math.random().toString(36).slice(2, 8)}`;
</script>

<Modal title="Update available" size="sm" role="alertdialog" describedby={descId} onclose={() => onclose(false)}>
  <div class="hero">
    <span class="orb fx-anim" aria-hidden="true"><Icon name="sparkles" size={30} /></span>
    <p class="versions mono" aria-label="Version {current} to version {version}">
      <span class="old">v{current}</span>
      <Icon name="chevron-right" size={14} />
      <span class="new">v{version}</span>
    </p>
  </div>
  <div id={descId} class="copy">
    <p>Version {version} is available (you have {current}).</p>
    <p>Download and install now?</p>
    <p class="muted small">The app will close and relaunch automatically. A running shift is kept and offered for recovery.</p>
  </div>
  {#snippet footer()}
    <Button variant="ghost" onclick={() => onclose(false)}>Later</Button>
    <Button variant="primary" glow icon="download" onclick={() => onclose(true)} data-autofocus>Install now</Button>
  {/snippet}
</Modal>

<style>
  .hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 4px 0 14px;
    text-align: center;
  }
  .orb {
    display: grid;
    place-items: center;
    width: 64px;
    height: 64px;
    border-radius: 50%;
    color: #fff;
    background: conic-gradient(from 0deg, var(--violet), var(--cyan), var(--magenta), var(--violet));
    box-shadow:
      0 0 0 6px color-mix(in srgb, var(--violet) 18%, transparent),
      0 10px 40px var(--accent-glow);
    animation: spin-hue 6s linear infinite;
  }
  .orb :global(svg) {
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.35));
  }
  @keyframes spin-hue {
    to {
      filter: hue-rotate(360deg);
    }
  }
  .versions {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 4px 12px;
    border-radius: var(--radius-pill);
    background: var(--neutral-fill);
    font-size: var(--fs-sm);
    color: var(--text-muted);
  }
  .new {
    color: var(--accent-text);
    font-weight: 700;
  }
  .copy {
    display: flex;
    flex-direction: column;
    gap: 6px;
    text-align: center;
  }
  .small {
    font-size: var(--fs-sm);
    margin-top: 4px;
  }
</style>

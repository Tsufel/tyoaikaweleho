/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

export default defineConfig(({ mode }) => ({
  base: './',
  plugins: [svelte()],
  build: {
    outDir: 'dist',
    target: 'chrome120',
    emptyOutDir: true,
    assetsInlineLimit: 0,
    chunkSizeWarningLimit: 600,
  },
  server: { port: 5173, strictPort: true },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.ts'],
    // Same wall clock on every machine (CI runners are UTC). TZ must also be
    // set for vi.unstubEnvs to restore it: deleting TZ doesn't reset Node's
    // timezone, so later tests would run in whatever zone a test stubbed.
    env: { TZ: 'Europe/Helsinki' },
  },
  resolve: mode === 'test' ? { conditions: ['browser'] } : undefined,
}));

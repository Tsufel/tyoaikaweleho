// Liquid glass: one place to tune the refracting surfaces.

/** Kill-switch for the SVG refraction tier; false ships the CSS-only tier. */
export const REFRACT_ENABLED = true;
/** Lenses beyond this fall back to the CSS tier for that element. */
export const MAX_LENSES = 6;

export type LensSpec = {
  bezel: number;
  shift: number;
  frost: number;
  dispersion?: boolean;
  mask?: 'rim' | 'full';
  zoom?: number;
  materialize?: boolean;
  light?: boolean;
};

export const SURFACES = {
  topbar: { bezel: 10, shift: 10, frost: 8, light: true },
  settingsTop: { bezel: 10, shift: 12, frost: 10, light: true },
  toast: { bezel: 8, shift: 10, frost: 10, materialize: true },
  popover: { bezel: 8, shift: 10, frost: 12, materialize: true },
  // no dispersion: its three displacement passes over a panel this size
  // stalled every frame on integrated GPUs while the page moved behind it
  modal: { bezel: 16, shift: 18, frost: 14, materialize: true, light: true },
  pill: { bezel: 13, shift: 10, frost: 0, mask: 'full', zoom: 1.15 },
} satisfies Record<string, LensSpec>;

export type SurfaceKey = keyof typeof SURFACES;

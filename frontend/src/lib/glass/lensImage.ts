// DOM half of the lens maps: field → PNG data URL. Tests never import this.
import { bezelLut, lensField, type FieldSpec, type LensField } from './lensMap';

/** DEV only: `?glassdebug` swaps every map for a hard left/right split, so
 *  the filter origin and region are visible (seam at the element centre). */
export function glassDebug(): boolean {
  return import.meta.env.DEV && typeof location !== 'undefined' && new URLSearchParams(location.search).has('glassdebug');
}

function splitField(ow: number, oh: number): LensField {
  const data = new Uint8ClampedArray(ow * oh * 4);
  for (let y = 0; y < oh; y++) {
    for (let x = 0; x < ow; x++) {
      const o = (y * ow + x) * 4;
      data[o] = x < ow / 2 ? 255 : 0;
      data[o + 1] = 128;
      data[o + 2] = 255;
      data[o + 3] = 255;
    }
  }
  return { data, ow, oh };
}

export function encodeLens(field: LensField): string {
  const c = document.createElement('canvas');
  c.width = field.ow;
  c.height = field.oh;
  const ctx = c.getContext('2d');
  if (!ctx) throw new Error('liquid glass: no 2D canvas context');
  ctx.putImageData(new ImageData(new Uint8ClampedArray(field.data), field.ow, field.oh), 0, 0);
  return c.toDataURL('image/png');
}

let lut: Float32Array | null = null;

/** The registry's generator: spec (without the LUT) → data URL. */
export function generateLens(spec: Omit<FieldSpec, 'lut'>, k: number): string {
  const field = lensField({ ...spec, lut: (lut ??= bezelLut()) }, k);
  return encodeLens(glassDebug() ? splitField(field.ow, field.oh) : field);
}

import { describe, expect, it } from 'vitest';
import { bezelLut, lensField, mapKey, mapScale, type FieldSpec } from '../src/lib/glass/lensMap';

const lut = bezelLut();
const spec = (o: Partial<FieldSpec> = {}): FieldSpec => ({ w: 101, h: 61, r: 20, b: 12, shift: 10, lut, ...o });

function px(f: { data: Uint8ClampedArray; ow: number }, x: number, y: number) {
  const o = (y * f.ow + x) * 4;
  return [f.data[o], f.data[o + 1], f.data[o + 2], f.data[o + 3]];
}

describe('bezelLut', () => {
  it('is finite, peaks at 1 and never rises', () => {
    expect(lut.every((v) => Number.isFinite(v))).toBe(true);
    expect(Math.max(...lut)).toBe(1);
    for (let i = 1; i < lut.length; i++) expect(lut[i]).toBeLessThanOrEqual(lut[i - 1]);
    expect(lut[lut.length - 1]).toBeLessThan(0.1);
  });
});

describe('lensField', () => {
  const f = lensField(spec());
  const midY = 30; // ly = 30.5 = h/2
  const midX = 50; // lx = 50.5 = w/2

  it('leaves the centre neutral without zoom', () => {
    expect(px(f, midX, midY)).toEqual([128, 128, 0, 255]);
  });

  it('bends edges inward', () => {
    const right = px(f, f.ow - 1, midY);
    expect(right[0]).toBeLessThan(128);
    expect(right[1]).toBe(128);
    expect(px(f, 0, midY)[0]).toBeGreaterThan(128);
    expect(px(f, midX, 0)[1]).toBeGreaterThan(128);
    expect(px(f, midX, f.oh - 1)[1]).toBeLessThan(128);
  });

  it('displaces a corner pixel on both axes toward the centre', () => {
    const [r, g] = px(f, 7, 7);
    expect(r).toBeGreaterThan(128);
    expect(g).toBeGreaterThan(128);
    const [r2, g2] = px(f, f.ow - 8, f.oh - 8);
    expect(r2).toBeLessThan(128);
    expect(g2).toBeLessThan(128);
  });

  it('is 4-way symmetric', () => {
    for (const y of [0, 5, midY]) {
      for (let x = 0; x < f.ow; x++) {
        const s = px(f, x, y)[0] + px(f, f.ow - 1 - x, y)[0];
        expect(s).toBeGreaterThanOrEqual(255);
        expect(s).toBeLessThanOrEqual(257);
      }
    }
    for (const x of [0, 5, midX]) {
      for (let y = 0; y < f.oh; y++) {
        const s = px(f, x, y)[1] + px(f, x, f.oh - 1 - y)[1];
        expect(s).toBeGreaterThanOrEqual(255);
        expect(s).toBeLessThanOrEqual(257);
      }
    }
  });

  it('keeps pixels deeper than the bezel neutral and frosted', () => {
    for (let x = 13; x < f.ow - 13; x++) expect(px(f, x, midY)).toEqual([128, 128, 0, 255]);
  });

  it('fades the rim mask monotonically across the band', () => {
    for (let x = 1; x <= 13; x++) expect(px(f, x, midY)[2]).toBeLessThanOrEqual(px(f, x - 1, midY)[2]);
    expect(px(f, 0, midY)[2]).toBeGreaterThan(200);
  });

  it("makes the whole lens sharp with mask 'full'", () => {
    const full = lensField(spec({ mask: 'full' }));
    for (let i = 2; i < full.data.length; i += 4) expect(full.data[i]).toBe(255);
  });

  it('magnifies toward the centre with zoom > 1', () => {
    const z = lensField(spec({ zoom: 1.2 }));
    expect(px(z, midX, midY)).toEqual([128, 128, 0, 255]);
    expect(px(z, midX + 20, midY)[0]).toBeLessThan(128);
    expect(px(z, midX - 20, midY)[0]).toBeGreaterThan(128);
  });

  it.each([
    ['capsule', spec({ r: 30.5 })],
    ['square corners', spec({ r: 0 })],
    ['1x1', spec({ w: 1, h: 1, r: 0.5 })],
    ['odd sizes', spec({ w: 77, h: 33, r: 9 })],
    ['bezel wider than radius', spec({ r: 6, b: 20 })],
    ['zoomed capsule', spec({ r: 30.5, zoom: 1.15, mask: 'full' })],
  ])('stays well formed: %s', (_n, s) => {
    const out = lensField(s);
    expect(out.data.length).toBe(out.ow * out.oh * 4);
    for (let i = 3; i < out.data.length; i += 4) expect(out.data[i]).toBe(255);
    // inward vectors only: left half never points left, top half never up
    for (let y = 0; y < out.oh; y++) {
      for (let x = 0; x < out.ow; x++) {
        const [r, g] = px(out, x, y);
        if (x < (out.ow - 1) / 2) expect(r).toBeGreaterThanOrEqual(128);
        if (y < (out.oh - 1) / 2) expect(g).toBeGreaterThanOrEqual(128);
      }
    }
  });

  it('rounds half-resolution dims up', () => {
    const half = lensField(spec(), 0.5);
    expect([half.ow, half.oh]).toEqual([51, 31]);
  });
});

describe('mapKey / mapScale', () => {
  it('builds id-safe keys that change with every input', () => {
    const { lut: _l, ...s } = spec();
    const k = mapKey(s, 1);
    expect(k).toMatch(/^lg-[0-9a-z.-]+$/);
    expect(mapKey({ ...s, shift: 11 }, 1)).not.toBe(k);
    expect(mapKey({ ...s, r: 20.5 }, 1)).not.toBe(k);
    expect(mapKey(s, 0.5)).not.toBe(k);
    expect(mapKey({ ...s, zoom: 1.15, mask: 'full' }, 1)).toMatch(/^lg-[0-9a-z.-]+$/);
  });

  it('halves big maps unless the lens zooms', () => {
    expect(mapScale(500, 600)).toBe(1);
    expect(mapScale(600, 600)).toBe(0.5);
    expect(mapScale(600, 600, 1.15)).toBe(1);
    expect(mapScale(100, 40, 1.15)).toBe(1);
  });
});

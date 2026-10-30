import { describe, expect, it } from 'vitest';
import { LightDriver, lightAngle, REST_ANGLE, unwrap } from '../src/lib/glass/light';

describe('lightAngle', () => {
  it('measures clockwise from straight up', () => {
    expect(lightAngle(0, -50, 0, 0)).toBe(0);
    expect(lightAngle(50, 0, 0, 0)).toBe(90);
    expect(lightAngle(0, 50, 0, 0)).toBe(180);
    expect(lightAngle(-50, 0, 0, 0)).toBe(270);
    // top-left is 315deg; 315 is not on the 6deg grid, so it lands within half a step
    expect(Math.abs(lightAngle(-50, -50, 0, 0) - 315)).toBeLessThanOrEqual(3);
    expect(lightAngle(-50, -50, 0, 0, 5)).toBe(315);
    expect(lightAngle(110, 90, 100, 100)).toBe(48);
  });

  it('quantises to 6 degree steps', () => {
    const at = (deg: number) => {
      const a = (deg * Math.PI) / 180;
      return lightAngle(100 * Math.sin(a), -100 * Math.cos(a), 0, 0);
    };
    expect(at(2)).toBe(0);
    expect(at(4)).toBe(6);
    expect(at(358)).toBe(0);
    expect(at(100)).toBe(102);
    expect(lightAngle(-50, -50, 0, 0, 10)).toBe(320);
  });
});

describe('unwrap', () => {
  it('takes the short way round', () => {
    expect(unwrap(350, 10)).toBe(370);
    expect(unwrap(10, 350)).toBe(-10);
    expect(unwrap(720, 90)).toBe(810);
    expect(unwrap(90, 120)).toBe(120);
  });
});

describe('LightDriver', () => {
  it('rests at 315 and clears its variable on unregister and stop', () => {
    expect(REST_ANGLE).toBe(315);
    const d = new LightDriver();
    const node = document.createElement('div');
    d.register(node);
    expect(d.size).toBe(1);
    node.style.setProperty('--lg-light', '90deg');
    d.unregister(node);
    expect(d.size).toBe(0);
    expect(node.style.getPropertyValue('--lg-light')).toBe('');

    d.register(node);
    const stop = d.start();
    node.style.setProperty('--lg-light', '90deg');
    stop();
    expect(node.style.getPropertyValue('--lg-light')).toBe('');
    d.unregister(node);
  });
});

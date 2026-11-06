// @vitest-environment node
import { describe, expect, it } from 'vitest';
import { earningsEquivalent } from '../src/views/timer/timerLogic';

describe('earningsEquivalent (#124)', () => {
  it('is quiet below one coffee and for bad amounts', () => {
    expect(earningsEquivalent(0)).toBeNull();
    expect(earningsEquivalent(3.49)).toBeNull();
    expect(earningsEquivalent(-5)).toBeNull();
    expect(earningsEquivalent(Number.NaN)).toBeNull();
  });

  it('picks the biggest thing that fits at least once', () => {
    expect(earningsEquivalent(3.5)).toBe("That's about 1 coffee");
    expect(earningsEquivalent(12.99)).toBe("That's about 3 coffees");
    expect(earningsEquivalent(13)).toBe("That's about 1 lunch buffet");
    expect(earningsEquivalent(59)).toBe("That's about 4 lunch buffets");
    expect(earningsEquivalent(160)).toBe("That's about 2 concert tickets");
    expect(earningsEquivalent(500)).toBe("That's about 2 weekends at a mökki");
  });
});

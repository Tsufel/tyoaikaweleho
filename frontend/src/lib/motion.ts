import { get } from 'svelte/store';
import { cubicOut, backOut } from 'svelte/easing';
import {
  fade as _fade,
  fly as _fly,
  scale as _scale,
  slide as _slide,
  type FadeParams,
  type FlyParams,
  type ScaleParams,
  type SlideParams,
  type TransitionConfig,
} from 'svelte/transition';
import { flip as _flip, type FlipParams } from 'svelte/animate';
import { motion } from './stores/motion';

/** True when animations should be skipped (OS setting or Reduce effects). */
export const reduced = () => get(motion) === 'reduced';

const instant = { duration: 0 };

/** Motion-aware wrappers of svelte/transition: duration 0 when reduced. */
export function fade(node: Element, p: FadeParams = {}): TransitionConfig {
  return _fade(node, reduced() ? instant : { duration: 180, ...p });
}
export function fly(node: Element, p: FlyParams = {}): TransitionConfig {
  return _fly(node, reduced() ? instant : { y: 8, duration: 260, easing: cubicOut, ...p });
}
export function scale(node: Element, p: ScaleParams = {}): TransitionConfig {
  return _scale(node, reduced() ? instant : { start: 0.96, duration: 220, easing: backOut, ...p });
}
export function slide(node: Element, p: SlideParams = {}): TransitionConfig {
  return _slide(node, reduced() ? instant : { duration: 220, easing: cubicOut, ...p });
}
/** Use with `animate:flip`. */
export function flip(node: Element, rects: { from: DOMRect; to: DOMRect }, p: FlipParams = {}) {
  return _flip(node, rects, reduced() ? instant : { duration: 260, easing: cubicOut, ...p });
}

/** Stagger delay for list item i (capped so long lists don't drag). */
export const stagger = (i: number, step = 28, max = 10) => (reduced() ? 0 : Math.min(i, max) * step);

/** Options for svelte/motion Spring; instant when reduced. */
export function springOpts(o: { stiffness?: number; damping?: number } = {}) {
  return reduced() ? { stiffness: 1, damping: 1, precision: 1e9 } : { stiffness: 0.12, damping: 0.55, ...o };
}

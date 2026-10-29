import type { MotionLevel } from '../../lib/stores/motion';

/** Whole pop-in → hold → slide-away run of the clock-out wizard. */
export const WIZARD_POP_MS = 2500;
export const WIZARD_LINE = 'sie oot weleho!';

/** Lulz-only flourish; never under reduced motion / Reduce effects. */
export const shouldPopWizard = (lulz: boolean, motion: MotionLevel) => lulz && motion === 'full';

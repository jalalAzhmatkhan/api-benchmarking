import { sleep } from 'k6';
import { THINK } from './config.js';

// T0: no think time (saturation). T1: uniform 0.5-1.5 s (mean 1 s), randomized so VUs do not
// move in lock-step (research findings §19).
export function think() {
  if (THINK === 'T1') sleep(0.5 + Math.random());
}

// Spread VU start times across the first second of a VU's first iteration.
export function stagger(isFirstIteration) {
  if (isFirstIteration) sleep(Math.random());
}

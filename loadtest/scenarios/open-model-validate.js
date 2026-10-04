// Open-model validation (k6 plan §7): constant arrival rate of S1 journeys at the closed-model
// throughput X* (iterations/s) measured at VU*. Reported, never used to pick VU*.
//   k6 run -e RATE=42 -e PRE_VUS=400 -e MEASURE_S=300 loadtest/scenarios/open-model-validate.js
import { openOptions, makeHandleSummary } from '../lib/options.js';
import { s1Journey } from '../lib/journeys.js';
import { MEASURE_S } from '../lib/config.js';

const RATE = parseFloat(__ENV.RATE || '10');
const PRE_VUS = parseInt(__ENV.PRE_VUS || '100', 10);
const MAX_VUS = parseInt(__ENV.MAX_VUS || String(PRE_VUS * 2), 10);

export const options = openOptions(RATE, MEASURE_S, PRE_VUS, MAX_VUS);
export default function () {
  s1Journey();
}
export const handleSummary = makeHandleSummary({ scenario: 'open-s1', rate: RATE, open: true });

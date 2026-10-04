// S2: read-heavy independent requests (SECONDARY). k6 plan §3.2.
import { levelOptions, makeHandleSummary } from '../lib/options.js';
import { s2Op } from '../lib/journeys.js';

export const options = levelOptions();
export default function () {
  s2Op();
}
export const handleSummary = makeHandleSummary({ scenario: 's2' });

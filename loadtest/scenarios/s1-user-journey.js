// S1: the 7-step user journey (PRIMARY). k6 plan §3.1.
//   k6 run -e BASE_URL=http://sut:8080 -e VUS=100 -e THINK=T0 loadtest/scenarios/s1-user-journey.js
import { levelOptions, makeHandleSummary } from '../lib/options.js';
import { s1Journey } from '../lib/journeys.js';

export const options = levelOptions();
export default function () {
  s1Journey();
}
export const handleSummary = makeHandleSummary({ scenario: 's1' });

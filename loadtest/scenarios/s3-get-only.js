// S3: GET-only diagnostic upper bound (OPTIONAL). k6 plan §3.3.
import { levelOptions, makeHandleSummary } from '../lib/options.js';
import { s3Op } from '../lib/journeys.js';

export const options = levelOptions();
export default function () {
  s3Op();
}
export const handleSummary = makeHandleSummary({ scenario: 's3' });

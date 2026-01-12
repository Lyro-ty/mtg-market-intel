import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const overviewDuration = new Trend('overview_duration');

export const options = {
  stages: [
    { duration: '1m', target: 100 },   // Ramp up to 100 VUs
    { duration: '2m', target: 100 },   // Steady state
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<1000'],  // Market overview can be slower (complex aggregations)
    errors: ['rate<0.01'],               // <1% errors
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  const res = http.get(`${BASE_URL}/api/market/overview`);

  overviewDuration.add(res.timings.duration);

  const success = check(res, {
    'status is 200': (r) => r.status === 200,
    'has total_cards': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.total_cards !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  errorRate.add(!success);
  sleep(2);
}

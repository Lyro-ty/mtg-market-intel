import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const searchDuration = new Trend('search_duration');

export const options = {
  stages: [
    { duration: '30s', target: 10 },   // Ramp up
    { duration: '1m', target: 50 },    // Steady state
    { duration: '30s', target: 100 },  // Peak
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% under 500ms
    errors: ['rate<0.01'],              // <1% errors
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const SEARCH_TERMS = ['lightning', 'bolt', 'counterspell', 'black lotus', 'force of will'];

export default function () {
  const term = SEARCH_TERMS[Math.floor(Math.random() * SEARCH_TERMS.length)];
  const res = http.get(`${BASE_URL}/api/cards/search?q=${encodeURIComponent(term)}&page_size=20`);

  searchDuration.add(res.timings.duration);

  const success = check(res, {
    'status is 200': (r) => r.status === 200,
    'has cards array': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.cards !== undefined && Array.isArray(body.cards);
      } catch (e) {
        return false;
      }
    },
    'response has pagination': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.total !== undefined && body.page !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  errorRate.add(!success);
  sleep(1);
}

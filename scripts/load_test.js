// k6 load test: constant number of virtual users hitting one endpoint.
// Env: BASE_URL (e.g. http://127.0.0.1:8000), ENDPOINT (/hello or /compute),
//      VUS (default 50), DURATION (default 30s)
import http from "k6/http";
import { check } from "k6";

export const options = {
  vus: Number(__ENV.VUS || 50),
  duration: __ENV.DURATION || "30s",
  summaryTrendStats: ["avg", "med", "p(95)", "p(99)", "max"],
};

export default function () {
  const res = http.get(`${__ENV.BASE_URL}${__ENV.ENDPOINT}`);
  check(res, { "status is 200": (r) => r.status === 200 });
}

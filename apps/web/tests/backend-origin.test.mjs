import assert from "node:assert/strict";
import { test } from "node:test";
import { backendRewrites } from "../lib/api/backend-origin.ts";

test("unconfigured local frontend has no proxy destination", () => {
  assert.deepEqual(backendRewrites(undefined), []);
});

test("explicit dedicated tunnel preserves all backend paths", () => {
  assert.deepEqual(backendRewrites("http://127.0.0.1:18082"), [{
    source: "/api/backend/:path*", destination: "http://127.0.0.1:18082/:path*",
  }]);
});

test("production API preserves the same-origin frontend proxy paths", () => {
  assert.deepEqual(backendRewrites("https://demandrift-api.ack-techs.com"), [{
    source: "/api/backend/:path*", destination: "https://demandrift-api.ack-techs.com/:path*",
  }]);
});

test("configuration cannot expose an arbitrary server-side proxy", () => {
  for (const value of ["", " http://127.0.0.1:18082", "http://127.0.0.1:18082/",
    "http://localhost:18082", "http://127.0.0.1:18083", "https://api.example.org",
    "http://private:secret@127.0.0.1:18082", "http://127.0.0.1:18082?key=secret",
    "http://127.0.0.1:18082#fragment", "http://127.0.0.1:18082\\@evil.example.org",
    "http://demandrift-api.ack-techs.com", "https://demandrift-api.ack-techs.com/",
    "https://demandrift-api.ack-techs.com:443", "https://demandrift-api.ack-techs.com/api/v1",
    " https://demandrift-api.ack-techs.com", "https://demandrift-api.ack-techs.com ",
    "https://private:secret@demandrift-api.ack-techs.com", "https://demandrift-api.ack-techs.com?key=secret",
    "https://demandrift-api.ack-techs.com#fragment", "https://demandrift-api.ack-techs.com.evil.example.org",
    "https://demandrift-api.ack-techs.com@evil.example.org", "https://demandrift-api.ack-techs.com\\@evil.example.org"])
    assert.throws(() => backendRewrites(value), /approved backend origin/);
});

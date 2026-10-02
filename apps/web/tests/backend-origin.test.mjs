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

test("configuration cannot expose an arbitrary server-side proxy", () => {
  for (const value of ["", " http://127.0.0.1:18082", "http://127.0.0.1:18082/",
    "http://localhost:18082", "http://127.0.0.1:18083", "https://api.example.org",
    "http://private:secret@127.0.0.1:18082", "http://127.0.0.1:18082?key=secret",
    "http://127.0.0.1:18082#fragment", "http://127.0.0.1:18082\\@evil.example.org"])
    assert.throws(() => backendRewrites(value), /dedicated loopback tunnel origin/);
});

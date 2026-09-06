import assert from "node:assert/strict";
import { ApiError, createApiClient } from "../src/shared/api/client.ts";

const originalFetch = globalThis.fetch;
const api = createApiClient("https://api.example.test/api/v1/");
let calls = 0;
let reply = () => Response.json({ ready: true });
let requestUrl: string | undefined;
let requestOptions: RequestInit | undefined;

globalThis.fetch = async (input, options) => {
  calls += 1;
  requestUrl = String(input);
  requestOptions = options;
  return reply();
};

try {
  const signal = new AbortController().signal;
  const result = await api<{ ready: boolean }>("/health/?probe=1", {
    method: "POST",
    body: { probe: true },
    headers: new Headers({ "X-Probe": "yes" }),
    credentials: "include",
    signal,
  });
  assert.equal(result.ready, true);
  assert.equal(requestUrl, "https://api.example.test/api/v1/health/?probe=1");
  assert.equal(requestOptions?.method, "POST");
  assert.equal(requestOptions?.body, '{"probe":true}');
  assert.equal(requestOptions?.credentials, "include");
  assert.equal(requestOptions?.signal, signal);
  const headers = new Headers(requestOptions?.headers);
  assert.equal(headers.get("Content-Type"), "application/json");
  assert.equal(headers.get("Accept"), "application/json");
  assert.equal(headers.get("X-Probe"), "yes");

  reply = () => new Response(null, { status: 204 });
  assert.equal(await api<void>("health/"), undefined);
  assert.equal(new Headers(requestOptions?.headers).has("Content-Type"), false);
  assert.equal(requestOptions?.body, undefined);
  assert.equal(requestOptions?.credentials, undefined);

  reply = () => Response.json({ detail: "Invalid input" }, { status: 400 });
  await assert.rejects(api("health/"), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 400);
    assert.deepEqual(error.data, { detail: "Invalid input" });
    return true;
  });

  reply = () => new Response("Bad gateway", { status: 502 });
  await assert.rejects(api("health/"), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 502);
    assert.equal(error.data, "Bad gateway");
    return true;
  });

  reply = () => new Response("invalid JSON");
  await assert.rejects(api("health/"), SyntaxError);
  const networkError = new TypeError("Network unavailable");
  reply = () => { throw networkError; };
  await assert.rejects(api("health/"), (error: unknown) => error === networkError);

  const callsBeforeValidation = calls;
  await assert.rejects(createApiClient(undefined)("health/"), /not configured/);
  await assert.rejects(api("../outside/"), /base URL/);
  await assert.rejects(api("https://other.example.test/"), /base URL/);
  await assert.rejects(createApiClient("file:///api/v1/")("health/"), /HTTP/);
  assert.equal(calls, callsBeforeValidation);

  console.log("API client check passed");
} finally {
  globalThis.fetch = originalFetch;
}

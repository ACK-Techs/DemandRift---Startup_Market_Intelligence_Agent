import { randomUUID } from "node:crypto";
import { request as httpRequest } from "node:http";
import type { ClientRequest, IncomingMessage } from "node:http";
import { backendRewrites } from "./backend-origin.ts";

export const backendRequestLimit = 64 * 1024;
export const backendResponseLimit = 10 * 1024 * 1024;
export const backendDeadlineMs = 45_000;
const headerLimit = 32 * 1024;
const methods = new Set(["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]);
const hopHeaders = new Set(["connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
  "te", "trailer", "transfer-encoding", "upgrade", "proxy-connection"]);
type FixtureControls = { port: number; deadlineMs?: number };
class ProxyFailure extends Error {
  readonly status: number;
  constructor(status: number) { super("Backend transport failed"); this.status = status; }
}

function failure(status: number) {
  return Response.json({ schema_version: "1.0.0", code: status === 504 ? "backend_timeout" :
    status === 503 ? "backend_unconfigured" : status === 413 ? "request_too_large" : "backend_connection_failed",
  message: "The backend request could not be completed. A submitted operation may still have committed; verify it explicitly.",
  request_id: randomUUID(), operation: "backend_proxy", stage: null, query_id: null, details_ref: null,
  source_id: null, retryable: false, retry_after_seconds: null, usage: null, remaining_work: [], next_step: null },
  { status, headers: { "Cache-Control": "no-store" } });
}

function blockedHeaders(pairs: [string, string][]) {
  const blocked = new Set(hopHeaders);
  for (const [name, value] of pairs) if (name.toLowerCase() === "connection") {
    for (const token of value.split(",")) blocked.add(token.trim().toLowerCase());
  }
  return blocked;
}

async function bodyBytes(request: Request, signal: AbortSignal): Promise<Buffer> {
  const declared = request.headers.get("content-length");
  if (declared !== null && (!/^\d+$/.test(declared) || !Number.isSafeInteger(Number(declared)))) throw new ProxyFailure(400);
  if (declared !== null && Number(declared) > backendRequestLimit) throw new ProxyFailure(413);
  if (!request.body) {
    if (declared !== null && Number(declared) !== 0) throw new ProxyFailure(400);
    return Buffer.alloc(0);
  }
  const reader = request.body.getReader(), chunks: Buffer[] = [];
  let length = 0, removeAbort = () => {};
  const cancelled = new Promise<never>((_, reject) => {
    const abort = () => { void reader.cancel().catch(() => {}); reject(new ProxyFailure(502)); };
    if (signal.aborted) abort();
    else signal.addEventListener("abort", abort, { once: true });
    removeAbort = () => signal.removeEventListener("abort", abort);
  });
  try {
    while (true) {
      const next = await Promise.race([reader.read(), cancelled]);
      if (next.done) break;
      length += next.value.byteLength;
      if (length > backendRequestLimit) { void reader.cancel().catch(() => {}); throw new ProxyFailure(413); }
      chunks.push(Buffer.from(next.value));
    }
    if (declared !== null && Number(declared) !== length) throw new ProxyFailure(400);
    return Buffer.concat(chunks, length);
  } finally { removeAbort(); reader.releaseLock(); }
}

/** Production caller supplies only the strict origin. Fixture controls are an explicit internal test seam, never an environment/request target. */
export function createBackendProxy(origin: string | undefined, fixture?: FixtureControls) {
  const configured = backendRewrites(origin).length !== 0;
  const port = fixture?.port ?? 18082, deadline = fixture?.deadlineMs ?? backendDeadlineMs;
  if (!Number.isInteger(port) || port < 1 || port > 65535 || !Number.isInteger(deadline) || deadline < 1 || deadline > backendDeadlineMs) {
    throw new Error("Invalid backend fixture controls");
  }
  return async function proxy(request: Request): Promise<Response> {
    if (!configured) return failure(503);
    if (!methods.has(request.method)) return failure(405);
    let path: string;
    try {
      const url = new URL(request.url), prefix = "/api/backend";
      path = url.pathname.slice(prefix.length);
      if (!url.pathname.startsWith(`${prefix}/`) || !/^\/[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)*$/.test(path) ||
        Buffer.byteLength(path) + Buffer.byteLength(url.search) > 8192) return failure(400);
      path += url.search;
    } catch { return failure(400); }
    const pairs = [...request.headers.entries()], blocked = blockedHeaders(pairs);
    const headers: Record<string, string> = {};
    let headerBytes = 0;
    for (const [name, value] of pairs) {
      headerBytes += Buffer.byteLength(name) + Buffer.byteLength(value) + 4;
      if (!blocked.has(name.toLowerCase()) && name.toLowerCase() !== "host" && name.toLowerCase() !== "content-length") headers[name] = value;
    }
    if (headerBytes > headerLimit) return failure(400);
    headers.connection = "close";
    const controller = new AbortController();
    let timedOut = false, upstream: ClientRequest | null = null, response: IncomingMessage | null = null;
    const cancel = () => { controller.abort(); upstream?.destroy(); response?.destroy(); };
    request.signal.addEventListener("abort", cancel, { once: true });
    const timer = setTimeout(() => { timedOut = true; cancel(); }, deadline);
    try {
      if (request.signal.aborted) cancel();
      const body = await bodyBytes(request, controller.signal);
      if (controller.signal.aborted) throw new ProxyFailure(502);
      if ((request.method === "GET" || request.method === "HEAD") && body.length) throw new ProxyFailure(400);
      if (body.length || request.headers.has("content-length")) headers["content-length"] = String(body.length);
      return await new Promise<Response>((resolve) => {
        let settled = false;
        const finish = (value: Response) => {
          if (settled) return;
          settled = true; controller.signal.removeEventListener("abort", aborted);
          resolve(value);
        };
        const fail = () => { if (settled) return; upstream?.destroy(); response?.destroy(); finish(failure(timedOut ? 504 : 502)); };
        const aborted = () => fail();
        controller.signal.addEventListener("abort", aborted, { once: true });
        try {
          // agent:false bypasses globalAgent and Next's independently constructed keepalive agent.
          // http.request performs exactly one attempt, including ambiguous mutation failures.
          upstream = httpRequest({ hostname: "127.0.0.1", port, path, method: request.method, headers,
            agent: false, maxHeaderSize: headerLimit }, (incoming) => {
            response = incoming;
            if (settled) { incoming.destroy(); return; }
            const status = incoming.statusCode ?? 502;
            if (status < 200 || status > 599 || [301, 302, 303, 307, 308].includes(status)) { fail(); return; }
            const raw: [string, string][] = [];
            for (let i = 0; i < incoming.rawHeaders.length; i += 2) raw.push([incoming.rawHeaders[i], incoming.rawHeaders[i + 1]]);
            const omitted = blockedHeaders(raw), outgoing = new Headers();
            for (const [name, value] of raw) if (!omitted.has(name.toLowerCase())) outgoing.append(name, value);
            // Buffered byte count replaces upstream framing; duplicate Set-Cookie remains separate in Headers.
            outgoing.delete("content-length"); outgoing.set("cache-control", "no-store");
            const chunks: Buffer[] = []; let length = 0;
            incoming.on("data", (chunk: Buffer) => {
              length += chunk.byteLength;
              if (length > backendResponseLimit) { fail(); return; }
              chunks.push(chunk);
            });
            incoming.once("aborted", fail); incoming.once("error", fail);
            incoming.once("end", () => {
              if (settled) return;
              if (!incoming.complete) { fail(); return; }
              try {
                const empty = request.method === "HEAD" || [204, 205, 304].includes(status);
                finish(new Response(empty ? null : Buffer.concat(chunks, length), { status, headers: outgoing }));
              } catch { fail(); }
            });
          });
          upstream.once("error", fail);
          if (controller.signal.aborted) { fail(); return; }
          upstream.end(body);
        } catch { fail(); }
      });
    } catch (error) { return failure(timedOut ? 504 : error instanceof ProxyFailure ? error.status : 502); }
    finally { clearTimeout(timer); request.signal.removeEventListener("abort", cancel); cancel(); }
  };
}

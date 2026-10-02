import { parseWire } from "./wire.ts";
import type { ModelName, Scope, WireModels } from "./wire.ts";
import { failureCategory, failureMessages } from "./status.ts";
import type { FailureCategory } from "./status.ts";

type Method = "GET" | "POST" | "PATCH" | "DELETE";
export type ApiResult<K extends ModelName> =
  | { ok: true; data: WireModels[K]; raw: string; status: number }
  | { ok: false; category: FailureCategory; message: string; status: number | null;
      operationState: "not_sent" | "rejected" | "unknown" | "cancelled";
      raw?: string; apiError?: WireModels["ApiError"] };
export type EmptyApiResult =
  | { ok: true; data: undefined; raw: ""; status: 204 }
  | Extract<ApiResult<ModelName>, { ok: false }>;
export type RequestOptions = {
  method?: Method; body?: unknown; query?: Record<string, string>; scope?: Scope;
  csrfToken?: string; idempotencyKey?: string; signal?: AbortSignal; timeoutMs?: number;
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const maxResponseBytes = 2 * 1024 * 1024;

function failure<K extends ModelName>(category: FailureCategory, state: Extract<ApiResult<K>, { ok: false }>["operationState"],
  status: number | null = null, raw?: string, apiError?: WireModels["ApiError"]): Extract<ApiResult<K>, { ok: false }> {
  return { ok: false, category, message: failureMessages[category], operationState: state, status, raw, apiError };
}

/** Fixed same-origin proxy only. Mutations are never automatically retried. */
export function createApiClient(fetcher: typeof fetch = fetch) {
  async function perform<K extends ModelName>(model: K, path: string, options: RequestOptions = {}, empty = false): Promise<ApiResult<K> | EmptyApiResult> {
      const method = options.method ?? "GET";
      const mutation = method !== "GET";
      const timeout = options.timeoutMs ?? 15000;
      if (!/^\/api\/v1\/[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)*$/.test(path) ||
          !["GET", "POST", "PATCH", "DELETE"].includes(method) ||
          !Number.isInteger(timeout) || timeout < 1 || timeout > 60000 ||
          (options.idempotencyKey !== undefined && !uuid.test(options.idempotencyKey)) ||
          (!mutation && options.body !== undefined)) return failure("validation", "not_sent");
      if (options.signal?.aborted) return failure("cancelled", "not_sent");
      let body: string | undefined;
      try { body = options.body === undefined ? undefined : JSON.stringify(options.body, (_key, value: unknown) => {
        if (value !== null && typeof value === "object") {
          let boxed = false;
          try { Number.prototype.valueOf.call(value); boxed = true; } catch { /* Other JSON objects. */ }
          if (boxed) throw new TypeError("Primitive JSON numbers are required");
        }
        if (typeof value === "number" && (!Number.isFinite(value) || (Number.isInteger(value) && !Number.isSafeInteger(value)))) {
          throw new TypeError("Unsafe numeric input");
        }
        return value;
      }); }
      catch { return failure("validation", "not_sent"); }
      const controller = new AbortController();
      let timedOut = false;
      const abort = () => controller.abort();
      options.signal?.addEventListener("abort", abort, { once: true });
      const timer = setTimeout(() => { timedOut = true; controller.abort(); }, timeout);
      const headers: Record<string, string> = { Accept: "application/json" };
      if (body !== undefined) headers["Content-Type"] = "application/json";
      if (mutation && options.csrfToken) headers["X-CSRF-Token"] = options.csrfToken;
      if (mutation && options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;
      const search = new URLSearchParams(options.query);
      const target = `/api/backend${path}${search.size ? `?${search}` : ""}`;
      try {
        const response = await fetcher(target, { method, body, headers,
          signal: controller.signal, credentials: "same-origin", cache: "no-store", redirect: "error" });
        const stream = response.body?.getReader();
        const chunks: Uint8Array[] = []; let bytes = 0;
        if (stream) {
          try {
            while (true) {
              const next = await stream.read(); if (next.done) break;
              bytes += next.value.byteLength;
              if (bytes > maxResponseBytes) { await stream.cancel(); return failure("contract", mutation ? "unknown" : "rejected", response.status); }
              chunks.push(next.value);
            }
          } finally { stream.releaseLock(); }
        }
        const content = new Uint8Array(bytes); let offset = 0;
        for (const chunk of chunks) { content.set(chunk, offset); offset += chunk.byteLength; }
        let raw: string;
        try { raw = new TextDecoder("utf-8", { fatal: true }).decode(content); }
        catch { return failure("contract", mutation ? "unknown" : "rejected", response.status); }
        if (empty && response.ok) {
          return response.status === 204 && raw === "" ? { ok: true, data: undefined, raw: "", status: 204 } :
            failure("contract", "unknown", response.status, raw);
        }
        const json = /^application\/(?:[a-z0-9.+-]+\+)?json(?:;|$)/i.test(response.headers.get("content-type") ?? "");
        if (!json) return failure("contract", mutation ? "unknown" : "rejected", response.status, raw);
        if (!response.ok) {
          const parsed = parseWire("ApiError", raw);
          return failure(failureCategory(response.status, parsed.ok ? parsed.data.code : undefined),
            mutation && response.status >= 500 ? "unknown" : "rejected", response.status, raw, parsed.ok ? parsed.data : undefined);
        }
        const parsed = parseWire(model, raw, options.scope);
        return parsed.ok ? { ok: true, data: parsed.data, raw, status: response.status } :
          failure("contract", mutation ? "unknown" : "rejected", response.status, raw);
      } catch {
        const category = controller.signal.aborted ? (timedOut ? "timeout" : "cancelled") : "network";
        return failure(category, mutation ? "unknown" : category === "cancelled" ? "cancelled" : "rejected");
      } finally {
        clearTimeout(timer); options.signal?.removeEventListener("abort", abort);
      }
  }
  return {
    request<K extends ModelName>(model: K, path: string, options: RequestOptions = {}): Promise<ApiResult<K>> {
      // This entry point always validates the requested JSON model.
      return perform(model, path, options) as Promise<ApiResult<K>>;
    },
    logout(csrfToken: string, options: Pick<RequestOptions, "signal" | "timeoutMs"> = {}): Promise<EmptyApiResult> {
      if (typeof csrfToken !== "string" || !/^[0-9a-f]{64}$/.test(csrfToken)) return Promise.resolve(failure("validation", "not_sent"));
      // Empty success is restricted to the canonical logout route and status.
      return perform("Session", "/api/v1/auth/logout", { ...options, method: "POST", csrfToken }, true) as Promise<EmptyApiResult>;
    },
  };
}

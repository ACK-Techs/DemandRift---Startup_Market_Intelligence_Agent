/** Server configuration for the dedicated Hetzner SSH tunnel. No credentials. */
export function backendRewrites(origin: string | undefined) {
  if (origin === undefined) return [];
  // Fix the destination rather than accepting a general-purpose proxy URL.
  // Exact matching rejects userinfo, fragments, redirects and alternate hosts.
  if (origin !== "http://127.0.0.1:18082") {
    throw new Error("DEMANDRIFT_BACKEND_ORIGIN must be the dedicated loopback tunnel origin");
  }
  return [{ source: "/api/backend/:path*", destination: `${origin}/:path*` }];
}

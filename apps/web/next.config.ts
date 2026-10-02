import type { NextConfig } from "next";
import { resolve } from "node:path";
import { backendRewrites } from "./lib/api/backend-origin.ts";

// Validate startup configuration; the server route owns transport without Next's external-rewrite agent.
backendRewrites(process.env.DEMANDRIFT_BACKEND_ORIGIN);

const nextConfig: NextConfig = {
  agentRules: false,
  turbopack: { root: resolve(__dirname, "../..") },
};

export default nextConfig;

import type { NextConfig } from "next";
import { resolve } from "node:path";
import { backendRewrites } from "./lib/api/backend-origin.ts";

const apiRewrites = backendRewrites(process.env.DEMANDRIFT_BACKEND_ORIGIN);

const nextConfig: NextConfig = {
  agentRules: false,
  turbopack: { root: resolve(__dirname, "../..") },
  async rewrites() { return apiRewrites; },
};

export default nextConfig;

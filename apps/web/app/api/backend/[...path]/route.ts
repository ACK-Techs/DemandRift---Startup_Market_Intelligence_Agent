import { createBackendProxy } from "@/lib/api/backend-proxy";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const proxy = createBackendProxy(process.env.DEMANDRIFT_BACKEND_ORIGIN);

export const GET = proxy;
export const HEAD = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;

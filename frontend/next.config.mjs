import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Pin the workspace root so Next doesn't walk up the filesystem to
  // auto-detect it. In Next 14.2.x this key lives under `experimental`;
  // the top-level form was added in Next 15.
  experimental: {
    outputFileTracingRoot: __dirname,
  },
  async rewrites() {
    // Trim whitespace and any trailing slash — a stray space in the
    // NEXT_PUBLIC_API_BASE_URL env var otherwise produces a rewrite
    // destination like " https://..." which Next rejects at build time
    // ("Invalid rewrite found"), and a trailing slash produces a
    // double slash in the proxied path.
    const backend = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000")
      .trim()
      .replace(/\/+$/, "");
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backend}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;

import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Pin the workspace root to this directory so Next doesn't walk up the
  // filesystem looking for a "real" project root (the auto-detection
  // misfires on Windows when Documents is OneDrive-synced or when a
  // stray lockfile exists at a parent path).
  outputFileTracingRoot: __dirname,
  // Force the @/* path alias to resolve from this directory regardless
  // of what Next thinks cwd is. Mirrors the tsconfig.json paths entry.
  webpack: (config) => {
    config.resolve = config.resolve || {};
    config.resolve.alias = {
      ...(config.resolve.alias ?? {}),
      "@": __dirname,
    };
    return config;
  },
  async rewrites() {
    const backend = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backend}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;

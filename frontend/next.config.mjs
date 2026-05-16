import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Pin the workspace root to this directory so Next doesn't walk up
  // the filesystem looking for a "real" project root.
  outputFileTracingRoot: __dirname,

  webpack: (config, { dev }) => {
    // Force the webpack compilation context to this directory.
    // Without this, on Windows Next can end up with context === drive
    // root, which sends Watchpack scanning C:\ and breaks tsconfig
    // path-alias resolution.
    config.context = __dirname;

    // The @/* alias (mirrors the tsconfig paths entry).
    config.resolve = config.resolve || {};
    config.resolve.alias = {
      ...(config.resolve.alias ?? {}),
      "@": __dirname,
    };

    // Watchpack on Windows otherwise tries to lstat C:\pagefile.sys
    // and other root-level system files. Belt-and-suspenders.
    if (dev) {
      config.watchOptions = {
        ...(config.watchOptions ?? {}),
        ignored: [
          "**/node_modules/**",
          "**/.next/**",
          "**/.git/**",
          "C:/DumpStack.log.tmp",
          "C:/hiberfil.sys",
          "C:/pagefile.sys",
          "C:/swapfile.sys",
        ],
      };
    }
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

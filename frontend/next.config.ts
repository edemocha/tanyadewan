import type { NextConfig } from "next";

// The FastAPI backend (uv run python -m tanyadewan.api) serves everything under /api. The frontend only
// proxies to it, so the browser talks to one origin and the SSE answer stream needs no CORS.
const API = process.env.TANYADEWAN_API ?? "http://127.0.0.1:8766";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};

export default nextConfig;

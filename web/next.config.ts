import type { NextConfig } from "next";

// In dev, proxy /api/* to the FastAPI server. On Vercel, vercel.json routes /api/* to the
// Python service before Next.js sees the request, so no rewrite is needed there.
const nextConfig: NextConfig = {
  async rewrites() {
    if (process.env.VERCEL) return [];
    const api = process.env.API_DEV_URL ?? "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};

export default nextConfig;

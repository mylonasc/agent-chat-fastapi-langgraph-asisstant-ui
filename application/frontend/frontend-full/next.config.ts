import type { NextConfig } from "next";

// Wheel builds set FULL_UI_BASE_PATH=/full (served under /full/ by FastAPI)
// and NEXT_PUBLIC_API_BASE="" (same-origin API). Dev/docker builds leave
// both unset and behave exactly as before.
const nextConfig: NextConfig = {
  // Static export so the full UI (thread sidebar, history) can be bundled
  // into the portable Python wheel and served same-origin by FastAPI.
  output: "export",
  trailingSlash: true,
  basePath: process.env.FULL_UI_BASE_PATH || undefined,
  images: {
    unoptimized: true,
  },
};

export default nextConfig;

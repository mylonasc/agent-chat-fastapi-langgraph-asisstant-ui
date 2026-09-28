import type { NextConfig } from "next";

// Wheel builds set NEXT_PUBLIC_API_BASE="" (same-origin API). Dev/docker
// builds leave it unset and behave exactly as before.
const nextConfig: NextConfig = {
  // Static export so the unified UI (minimal/full presets selected at
  // runtime via /api/config) can be bundled into the portable Python
  // wheel and served same-origin by FastAPI.
  output: "export",
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
};

export default nextConfig;

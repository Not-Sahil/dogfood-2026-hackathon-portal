import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    unoptimized: true,
  },
  allowedDevOrigins: ["**.manuspre.computer", "*.sg2.manus.computer"],
  async rewrites() {
    const backendOrigin =
      process.env.API_INTERNAL_URL?.trim() || "http://127.0.0.1:8000";

    return [
      {
        source: "/api/:path*",
        destination: `${backendOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;

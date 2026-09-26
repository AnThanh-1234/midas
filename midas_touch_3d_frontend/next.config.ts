import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: false,
  async rewrites() {
    return [
      {
        source: '/mediapipe/face_mesh/:path*',
        destination: 'https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/:path*',
      },
    ];
  },
};

export default nextConfig;

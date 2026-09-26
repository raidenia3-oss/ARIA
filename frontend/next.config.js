/** @type {import('next').NextConfig} */
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  // output: 'export' se aplica vía next.config.android.js para el build APK.
  async rewrites() {
    return [
      {
        source: "/ame",
        destination: "/ame",
      },
      {
        source: "/ame/:path*",
        destination: "/ame/:path*",
      },
      {
        source: "/api/health",
        destination: "/api/health",
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/api/:path*",
        headers: [
          {
            key: "Access-Control-Allow-Origin",
            value:
              process.env.NEXT_PUBLIC_SITE_URL ||
              "https://aura-web-chi-seven.vercel.app",
          },
          {
            key: "Access-Control-Allow-Methods",
            value: "GET,POST,PUT,DELETE,OPTIONS",
          },
          {
            key: "Access-Control-Allow-Headers",
            value: "Content-Type,Authorization",
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;

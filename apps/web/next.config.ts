import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  experimental: {
    typedRoutes: true,
  },
};

export default config;

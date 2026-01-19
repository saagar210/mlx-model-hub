import type { NextConfig } from "next";
import withSerwistInit from "@serwist/next";

const withSerwist = withSerwistInit({
  swSrc: "src/sw.ts",
  swDest: "public/sw.js",
  disable: process.env.NODE_ENV === "development",
});

const nextConfig: NextConfig = {
  // Empty turbopack config to silence warning about webpack config from Serwist
  // Serwist is disabled in dev mode, so Turbopack works fine
  turbopack: {},
};

export default withSerwist(nextConfig);

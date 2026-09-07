/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The dev badge sits bottom-left, exactly on top of the provenance
  // cartouche, and it covered the citation in every review capture. Provenance
  // is a hard requirement (CLAUDE.md), so nothing may occlude it -- including
  // a tool affordance that only exists in development.
  devIndicators: false,
  // Cesium's static assets (Workers/Assets/ThirdParty/Widgets) are copied into
  // public/cesium by scripts/copy-cesium.mjs and located at runtime via
  // window.CESIUM_BASE_URL. Nothing is fetched from cesium.com, which is what
  // makes OFFLINE=1 (PRD F11) true for the globe as well as the data.
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000",
    NEXT_PUBLIC_CESIUM_BASE: "/cesium",
  },
};
export default nextConfig;

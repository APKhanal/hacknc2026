/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Playwright ships native browser binaries; keep the bundler from trying
  // to inline them (used by app/api/chart/[run_id]/route.ts).
  serverExternalPackages: ["playwright"],
};

export default nextConfig;

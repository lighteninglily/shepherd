/**
 * Next.js configuration to improve stability on Windows + Dropbox
 * - Uses a custom distDir to avoid stale .next collisions
 * - Leaves watcher behavior primarily to environment variables set by scripts/dev.ps1
 */

/** @type {import('next').NextConfig} */
const config = {
  distDir: '.next-dev',
  reactStrictMode: true,
};

export default config;

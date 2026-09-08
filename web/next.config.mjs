/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Les types partages vivent hors du dossier `web` : Next doit les transpiler.
  transpilePackages: ["@koda/shared"],
  outputFileTracingRoot: new URL("..", import.meta.url).pathname,
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;

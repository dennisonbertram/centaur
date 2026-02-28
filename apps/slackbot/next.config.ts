import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(import.meta.dirname),
  transpilePackages: ["shiki"],
  experimental: {
    reactCompiler: true,
  },
};

export default nextConfig;

// 生产（Sealos）前端配置：启用 standalone 输出 + 内网 rewrite
// 构建时复制本文件到 frontend/next.config.ts 覆盖开发配置
// BACKEND_URL 运行时从环境变量读取（默认 Sealos 内网服务名），
// 浏览器侧 /api/v1、/health、/static 请求走同域 Ingress，不经过 rewrite。
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    const backendUrl =
      process.env.BACKEND_URL || "http://dwell-backend:8000";
    return [
      { source: "/api/v1/:path*", destination: `${backendUrl}/api/v1/:path*` },
      { source: "/health", destination: `${backendUrl}/health` },
      { source: "/static/:path*", destination: `${backendUrl}/static/:path*` },
    ];
  },
};

export default nextConfig;

import React from "react";

/**
 * 公共路由 Providers
 *
 * 注意：这个组件现在是空的，因为 ThemeProvider 和 AuthProvider
 * 已经提升到 App.tsx 顶层统一管理
 *
 * 首页、隐私政策、服务条款、登录、注册等公共路由
 * 不需要额外的 Context（Theme、Auth、SEO 都在顶层）
 */
export function CommonProviders({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

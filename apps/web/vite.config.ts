import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import sitemapPlugin from 'vite-plugin-sitemap'
import { visualizer } from 'rollup-plugin-visualizer'
import path from 'path'

const apiProxyTarget = (process.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')
const allowedHosts = (process.env.VITE_ALLOWED_HOSTS || 'localhost,127.0.0.1')
  .split(',')
  .map((host) => host.trim())
  .filter(Boolean)

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    sitemapPlugin({
      // 从环境变量读取 hostname,开发环境用 localhost
      hostname: process.env.VITE_BASE_URL || 'http://localhost:5173',
      // 添加 SPA 路由(不是实际 HTML 文件)
      dynamicRoutes: [
        '/privacy-policy',
        '/terms-of-service',
      ],
      // 排除需要登录的页面
      exclude: [
        '/login',
        '/register',
        '/dashboard',
        '/profile',
        '/project/',
        '/verify-email',
        '/auth',
      ],
      // 配置页面更新频率
      changefreq: 'weekly',
      // 配置页面优先级
      priority: {
        '/': 1.0,
        '/privacy-policy': 0.5,
        '/terms-of-service': 0.5,
      },
      // robots.txt 由 public/robots.txt 单独管理
      generateRobotsTxt: false,
    }),
    visualizer({
      open: true,
      gzipSize: true,
      brotliSize: true,
    }),
  ],
  build: {
    // 代码分割配置
    rollupOptions: {
      output: {
        manualChunks: {
          // React 核心库分离 - 缓存利用率高
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],

          // UI 库分离 - 首页不需要的库
          'ui-vendor': ['lucide-react', 'clsx', 'tailwind-merge'],

          // 状态管理分离 - Dashboard 需要但首页不需要
          'state-vendor': ['zustand', '@tanstack/react-query'],

          // Editor 库分离 - 首页不需要
          'editor-vendor': ['@tiptap/react', '@tiptap/starter-kit', '@tiptap/extension-placeholder'],

          // i18n 库分离
          'i18n-vendor': ['i18next', 'react-i18next'],

          // Markdown 渲染库分离
          'markdown-vendor': ['react-markdown', 'remark-gfm'],

          // 工具库分离
          'utils-vendor': ['diff-match-patch', 'axios'],
        },
      },
    },

    // CSS 代码分割
    cssCodeSplit: true,

    // 调整 chunk 大小警告阈值
    chunkSizeWarningLimit: 1000,

    // 压缩配置 - 使用 esbuild (Vite 默认)
    minify: 'esbuild',
  },

  // 依赖预构建优化 - 移除 force: true
  optimizeDeps: {
    // 只预构建必要依赖
    include: [
      'react',
      'react-dom',
      'react-router-dom',
    ],
    // 排除不需要预构建的库
    exclude: [],
  },

  resolve: {
    dedupe: ['react', 'react-dom', 'react-router-dom'],
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  server: {
    allowedHosts,
    hmr: true,
    proxy: {
      '/api': {
        target: apiProxyTarget,
        changeOrigin: true,
      },
    },
  },
})

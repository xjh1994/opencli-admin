import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 8030,
    // Allow requests from Docker containers (host.docker.internal) and any LAN IP
    // Dev-only: production uses nginx which doesn't have this restriction
    allowedHosts: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8031',
        changeOrigin: true,
        ws: true,
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            // Pass original host so the API can build correct public URLs (e.g. install scripts)
            const host = req.headers['host']
            if (host) {
              proxyReq.setHeader('X-Forwarded-Host', host)
              proxyReq.setHeader('X-Forwarded-Proto', 'http')
            }
          })
        },
      },
    },
  },
})

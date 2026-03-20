import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
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

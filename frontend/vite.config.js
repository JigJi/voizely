import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api/auth/login': 'http://127.0.0.1:8810',
      '/api': {
        target: 'https://voizely-backend.tailb8d083.ts.net',
        changeOrigin: true,
        secure: true,
      },
      '/htmx': {
        target: 'https://voizely-backend.tailb8d083.ts.net',
        changeOrigin: true,
        secure: true,
      },
    },
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy to the steward API; in ECS the ALB routes /api to the FastAPI service.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: process.env.VITE_API_URL ?? 'http://127.0.0.1:8000', changeOrigin: true } },
  },
})

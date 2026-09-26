import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dev server forwards /api (including the chat WebSocket) to the FastAPI
// process started from backend/, so the browser always talks to one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_ORIGIN ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
      },
    },
  },
})

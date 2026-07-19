/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5000,
    // Fail loudly instead of silently picking 5001/5002/... when 5000 is
    // taken (e.g. by a leftover dev server, or macOS's AirPlay Receiver,
    // which squats on 5000 by default -- disable it in System Settings ->
    // General -> AirDrop & Handoff if it's the culprit) -- README always
    // says "open localhost:5000" and a silently different port breaks that.
    strictPort: true,
    // Lets the frontend call same-origin relative /api/* URLs even in dev
    // mode, where Vite (5000) and FastAPI (8081) are different origins --
    // matches production, where the backend serves this build itself and
    // /api/* really is same-origin. Override with VITE_API_BASE_URL if the
    // backend isn't on localhost:8081.
    proxy: {
      '/api': process.env.VITE_API_BASE_URL || 'http://localhost:8081',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
})

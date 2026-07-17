/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5000,
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

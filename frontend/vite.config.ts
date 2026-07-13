/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Lets the frontend call same-origin relative /api/* URLs even in dev
    // mode, where Vite (5173) and FastAPI (8000) are different origins --
    // matches production, where the backend serves this build itself and
    // /api/* really is same-origin. Override with VITE_API_BASE_URL if the
    // backend isn't on localhost:8000.
    proxy: {
      '/api': process.env.VITE_API_BASE_URL || 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
  },
})

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// Proxying /api to the FastAPI backend means the frontend code always
// calls relative "/api/..." paths -- no base-URL config needed, and it
// works unchanged whether Vite is proxying (dev) or FastAPI is serving
// the built assets directly (prod, see Dockerfile).
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})

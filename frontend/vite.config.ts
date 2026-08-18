import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5174,
    proxy: {
      '/api': 'http://127.0.0.1:8001',
      '/media': 'http://127.0.0.1:8001',
      '/share': 'http://127.0.0.1:8001',
    },
  },
})

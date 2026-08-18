import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const assetBase = process.env.VITE_ASSET_BASE || '/'

export default defineConfig({
  plugins: [vue()],
  base: assetBase.endsWith('/') ? assetBase : `${assetBase}/`,
  optimizeDeps: {
    include: ['pixi.js', 'pixi-live2d-display'],
  },
  server: {
    port: 5174,
    proxy: {
      '/api': 'http://127.0.0.1:8001',
      '/media': 'http://127.0.0.1:8001',
      '/share': 'http://127.0.0.1:8001',
    },
  },
})

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5175,
    allowedHosts: true,    // allow tunnel URLs (cloudflare, ngrok, etc.)
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('recharts') || id.includes('d3-')) return 'charts'
          if (
            id.includes('@radix-ui') || id.includes('lucide-react') ||
            id.includes('class-variance-authority') || id.includes('/clsx/') ||
            id.includes('tailwind-merge')
          ) return 'ui-vendor'
          return 'vendor'
        },
      },
    },
  },
})

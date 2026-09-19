import path from 'node:path'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      // Sample RFP .txt files live in ../data/sample_rfps, outside this
      // package root — widen Vite's allow-list so `?raw` imports can reach them.
      allow: [path.resolve(dirname, '..')],
    },
  },
})

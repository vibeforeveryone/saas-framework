import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'


export default defineConfig({
  plugins: [react()],
 
 
  server: {
    port: 3000,
 
    // Replaces the top-level "proxy" field that CRA read from package.json.
    proxy: {
      '/api/': {
        target: 'http://localhost:3001',
        changeOrigin: true,
      },
    },
  },
 
  build: {
    // Keeps the same output folder name as CRA so any deployment scripts
    // that reference the 'build/' directory continue to work unchanged.
    outDir: 'build',
  },
});

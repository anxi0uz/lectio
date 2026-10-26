import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  build: {
    outDir: 'dist/client',
  },
  optimizeDeps: {
    include: ['react', 'react-dom/client'],
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.LECTIO_API_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: 660000,
      },
    },
    allowedHosts: ['terminal.local'],
    warmup: {
      clientFiles: ['./src/main.jsx'],
    },
  },
  plugins: [react()],
});

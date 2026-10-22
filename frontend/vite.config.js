import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Keep the heavy charting library out of the main bundle so the app shell loads first.
        manualChunks: { recharts: ['recharts'], vendor: ['react', 'react-dom', 'react-router-dom', 'axios'] },
      },
    },
  },
  server: {
    port: 5173,
    // The backend's CORS allow-list names this exact origin; silently moving to
    // another port (5174, ...) would make every API call fail CORS.
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});

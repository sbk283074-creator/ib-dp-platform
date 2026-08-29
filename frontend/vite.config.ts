import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  // Relative base so built assets load correctly under any GitHub Pages
  // subpath (e.g. /<repo>/) as well as from the Netlify root.
  base: './',
  plugins: [react()],
  server: {
    host: true,       // listen on 0.0.0.0 so LAN devices (phone/iPad) can connect
    port: 5175,
    strictPort: true, // fail loudly instead of silently switching ports
    proxy: {
      '/api': 'http://localhost:3001',
      '/figures': 'http://localhost:3001'
    }
  }
});

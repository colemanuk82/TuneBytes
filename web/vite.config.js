import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import mkcert from 'vite-plugin-mkcert';

// https://vitejs.dev/config/
export default defineConfig(({ command }) => ({
    plugins: [
        react(),
        command === "serve" ? mkcert() : null // Local SSL certificates are only needed for development.
    ].filter(Boolean),
    server: {
        https: true, // Forces Vite to use https:// instead of http://
        host: true,  // Exposes your server to your local network (0.0.0.0) so your phone can find it
        port: 5173,  // You can specify your preferred port here
    },
}));

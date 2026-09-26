import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

// Build estático para ser servido por FastAPI desde la raíz ("/").
// Usamos base relativa "./" para que los assets carguen sin importar el dominio.
export default defineConfig({
    plugins: [react()],
    base: "./",
    server: {
        port: 5173,
        open: false,
        proxy: {
            // En desarrollo, redirige las llamadas de API al backend real.
            "/api": { target: BACKEND, changeOrigin: true },
            "/health": { target: BACKEND, changeOrigin: true },
            "/ws": { target: BACKEND, ws: true, changeOrigin: true },
        },
    },
    build: {
        outDir: "dist",
        emptyOutDir: true,
    },
});

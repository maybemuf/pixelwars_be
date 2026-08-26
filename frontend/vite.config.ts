import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";
import { defineConfig } from "vite";

// Dev-only proxy: keeps the API same-origin so the session cookie is sent.
// In the container nginx does the same job (see nginx.conf).
const proxy = { target: "http://localhost:8000", changeOrigin: true };

export default defineConfig({
  plugins: [react(), tailwind()],
  server: { host: true, port: 5173, proxy: { "/boards": proxy, "/auth": proxy, "/health": proxy } },
});

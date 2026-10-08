import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173 },
  build: { chunkSizeWarningLimit: 900 }, // Recharts pesa ~400 kB; el panel admin ya se separa con lazy()
});

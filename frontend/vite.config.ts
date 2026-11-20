import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development ("npm run dev"), /api is forwarded to the API on port 8000,
// the same way nginx forwards it in the container.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Pin the host and port. The backend only allows CORS from
    // localhost:5173 and only redirects back there after OAuth, so if Vite
    // quietly moved to 5174 the app would break in a confusing way.
    // strictPort makes it fail loudly instead.
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
});

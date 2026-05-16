import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // host: true,  // re-enable to expose on the LAN. Note: Google OAuth
    // only accepts requests from origins listed in your OAuth client.
  },
});

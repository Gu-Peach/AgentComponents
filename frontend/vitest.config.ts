import { defineConfig } from "vitest/config";
export default defineConfig({
  resolve: {
    alias: {
      "@": import.meta.dirname,
    },
  },
  test: {
    environment: "node",
    globals: true,
    include: ["test/**/*.test.ts", "test/**/*.test.tsx"],
  },
});

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // The only directory `src/docket/api/app.py` mounts a static SPA from
    // (plan 07 Task 5 fix round 1, I5). The built bundle is never committed — see
    // the matching `.gitignore` entry — Task 9's `docket ui`/`make demo` build it
    // here when it's missing.
    outDir: '../src/docket/api/static',
    emptyOutDir: true,
  },
  server: {
    // The FastAPI service (src/docket/api) serves the built SPA in production;
    // in dev, proxy API and SSE calls to uvicorn so the browser only ever talks
    // to one origin.
    proxy: {
      '/api': 'http://127.0.0.1:8766',
    },
  },
});

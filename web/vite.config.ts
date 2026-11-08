import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// docs/api-mock.json lives one level up; allow the dev server to read it.
export default defineConfig({
  base: '/dashboard/', // served by the FastAPI app at /dashboard/ (the jury hub owns /)
  plugins: [react()],
  server: { fs: { allow: ['..'] } },
})

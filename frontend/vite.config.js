import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth': 'http://localhost:8000',
      '/cv': 'http://localhost:8000',
      '/requirements': 'http://localhost:8000',
      '/assessment': 'http://localhost:8000',
      '/ml': 'http://localhost:8000',
      '/users': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})

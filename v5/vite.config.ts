import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import electron from 'vite-plugin-electron/simple'
import { resolve } from 'path'

export default defineConfig(({ mode, command }) => {
  const isDev = mode === 'development' && command === 'serve'

  return {
    root: '.',
    plugins: [
      react(),
      electron({
        main: {
          entry: 'electron/main.ts',
          vite: {
            build: {
              outDir: 'dist-electron',
              rollupOptions: {
                output: { format: 'cjs' },
                external: ['electron', 'electron/main'],
              },
            },
          },
          onstart(args) {
            if (process.env.VITE_DEV_SERVER_URL) {
              args.startupArgs = [process.env.VITE_DEV_SERVER_URL]
            }
          },
        },
        preload: {
          input: 'electron/preload.ts',
          vite: {
            build: {
              outDir: 'dist-electron',
            },
          },
        },
      }),
    ],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
        '@electron': resolve(__dirname, 'electron'),
      },
    },
    build: {
      outDir: 'dist',
      chunkSizeWarningLimit: 2000,
      rollupOptions: {
        output: {
          manualChunks: {
            'react-vendor': ['react', 'react-dom'],
            'three-vendor': ['three'],
            'motion': ['framer-motion'],
          },
        },
      },
    },
    server: {
      port: 5173,
      strictPort: true,
    },
  }
})

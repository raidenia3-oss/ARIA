/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        aura: {
          bg: '#05070a',
          surface: '#0a0f14',
          panel: '#0d1117',
          border: 'rgba(56, 189, 248, 0.25)',
          primary: '#38bdf8',
          secondary: '#6366f1',
          accent: '#22d3ee',
          danger: '#ef4444',
          success: '#22c55e',
          warning: '#facc15',
          muted: '#94a3b8',
        }
      },
      boxShadow: {
        'neon': '0 0 15px rgba(56, 189, 248, 0.35)',
        'neon-strong': '0 0 25px rgba(56, 189, 248, 0.6)',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow': 'spin 8s linear infinite',
      }
    },
  },
  plugins: [],
}

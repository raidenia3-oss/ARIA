/* ARIA Cosmic-Inspired UI - Tailwind config additions */

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
    "./electron/**/*.ts"
  ],
  theme: {
    extend: {
      colors: {
        // Cosmic-inspired palette
        'bg-dark-0': '#0a0e27',
        'bg-dark-1': '#0f172a',
        'bg-dark-2': '#141e3f',
        'surface-0': '#1e293b',
        'surface-1': '#273449',
        'border': '#334155',
        'border-bright': '#475569',
        
        // ARIA accent colors
        'accent-cyan': 'var(--color-accent-cyan)',
        'accent-cyan-bright': 'var(--color-accent-cyan-bright)',
        'accent-purple': 'var(--color-accent-purple)',
        'accent-green': '#00ff88',
        'accent-orange': '#ff6b4a',
        
        // Cosmic-inspired semantic colors
        'cosmic-primary': '#38bdf8',    // cyan - actions
        'cosmic-accent': '#a78bfa',     // purple - highlights
        'cosmic-success': '#34d399',    // green - positive
        'cosmic-warning': '#fbbf24',    // amber - caution
        'cosmic-error': '#ef4444',      // red - critical
        
        // Text
        'text-primary': '#ffffff',
        'text-secondary': '#cbd5e1',
        'text-tertiary': '#94a3b8',
        'text-muted': '#64748b',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'breathing': 'breathing 1.5s ease-in-out infinite',
        'glow-pulse': 'glow-pulse 2s ease-in-out infinite',
        'orbit': 'orbit 6s linear infinite',
        'pulse-ring': 'pulse-ring 2s ease-out infinite',
        'fade-in': 'fade-in 200ms ease-out',
        'slide-up': 'slide-up 200ms ease-out',
        'float': 'float 3s ease-in-out infinite',
        'scanline': 'scanline 8s linear infinite',
      },
      keyframes: {
        breathing: {
          '0%, 100%': { opacity: '0.7', transform: 'scale(1)' },
          '50%': { opacity: '0.95', transform: 'scale(1.05)' },
        },
        'glow-pulse': {
          '0%, 100%': { 'box-shadow': '0 0 10px rgba(56, 189, 248, 0.5)' },
          '50%': { 'box-shadow': '0 0 20px rgba(0, 212, 255, 0.8)' },
        },
        orbit: {
          '0%': { transform: 'rotate(0deg) translateX(60px) rotate(0deg)' },
          '100%': { transform: 'rotate(360deg) translateX(60px) rotate(-360deg)' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(1)', opacity: '0.8' },
          '100%': { transform: 'scale(2.5)', opacity: '0' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-up': {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        scanline: {
          '0%': { 'background-position': '0 0' },
          '100%': { 'background-position': '0 100%' },
        },
      },
      backdropBlur: {
        xs: '2px',
        sm: '4px',
        md: '8px',
        lg: '16px',
        xl: '24px',
        '2xl': '32px',
        '3xl': '48px',
      },
      backgroundImage: {
        'cosmic-gradient': 'linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)',
        'glass-gradient': 'linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.8) 100%)',
      },
      boxShadow: {
        'glass': '0 8px 32px rgba(0, 0, 0, 0.3)',
        'glow-cyan': '0 0 20px rgba(56, 189, 248, 0.4)',
        'glow-purple': '0 0 20px rgba(167, 139, 250, 0.4)',
        'glow-green': '0 0 20px rgba(52, 211, 153, 0.4)',
      },
    }
  },
  plugins: [],
}
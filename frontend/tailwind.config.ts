import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        chimera: {
          bg: '#0f0f1a',
          'bg-secondary': '#1a1a2e',
          'bg-card': 'rgba(255, 255, 255, 0.05)',
          'bg-card-hover': 'rgba(255, 255, 255, 0.08)',
          border: 'rgba(255, 255, 255, 0.08)',
          'border-active': 'rgba(255, 255, 255, 0.15)',
          accent: '#C8956C',
          'accent-hover': '#D4A574',
          'accent-glow': 'rgba(200, 149, 108, 0.2)',
          cyan: '#06B6D4',
          purple: '#8B5CF6',
          text: '#E2E8F0',
          'text-secondary': '#94A3B8',
          muted: '#64748B',
          success: '#22C55E',
          'success-bg': 'rgba(34, 197, 94, 0.1)',
          error: '#EF4444',
          'error-bg': 'rgba(239, 68, 68, 0.1)',
          warning: '#EAB308',
          'warning-bg': 'rgba(234, 179, 8, 0.1)',
          inplay: '#F59E0B',
        },
      },
      fontFamily: {
        sans: ['Lexend', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      backdropBlur: {
        xs: '2px',
      },
      animation: {
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}

export default config

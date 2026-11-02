/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Slate-based dark theme
        background: {
          DEFAULT: '#0f1115',
          secondary: '#16191f',
          tertiary: '#1e2129',
        },
        surface: {
          DEFAULT: '#1e2129',
          hover: '#262a33',
          border: '#2d313a',
        },
        text: {
          primary: '#e8eaed',
          secondary: '#9aa4b2',
          muted: '#6b7280',
        },
        accent: {
          DEFAULT: '#3b82f6', // blue-500
          hover: '#2563eb', // blue-600
          light: '#60a5fa', // blue-400
        },
        severity: {
          critical: '#ef4444', // red-500
          high: '#f97316', // orange-500
          medium: '#eab308', // yellow-500
          low: '#22c55e', // green-500
          info: '#3b82f6', // blue-500
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-in': 'slideIn 0.3s ease-out',
        'pulse-soft': 'pulseSoft 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { transform: 'translateX(-10px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.7' },
        },
      },
    },
  },
  plugins: [],
}
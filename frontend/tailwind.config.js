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
        background: {
          DEFAULT: '#11132F',
          secondary: '#171A3A',
          tertiary: '#202143',
        },
        surface: {
          DEFAULT: '#202143',
          hover: '#292B55',
          border: '#383A67',
        },
        text: {
          primary: '#F3F1FF',
          secondary: '#B9B8D8',
          muted: '#8989B4',
        },
        accent: {
          DEFAULT: '#8B5CF6',
          hover: '#9878FF',
          light: '#B9A6FF',
        },
        sidebar: {
          DEFAULT: '#292950',
          secondary: '#343365',
          active: '#6040C7',
          accent: '#A58AFF',
        },
        workspace: {
          DEFAULT: '#7775AD',
        },
        status: {
          cyan: '#48C8DD',
          success: '#4FCB91',
          warning: '#E9C957',
          danger: '#E6787D',
        },
        severity: {
          critical: '#E6787D',
          high: '#D85F73',
          medium: '#E9C957',
          low: '#48C8DD',
          info: '#8989B4',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Cascadia Code', 'Consolas', 'monospace'],
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

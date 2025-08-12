import typography from '@tailwindcss/typography'

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef6ff',
          100: '#d9eaff',
          200: '#bcd8ff',
          300: '#8fbfff',
          400: '#5a9cff',
          500: '#2f74ff',
          600: '#1959e6',
          700: '#1546b3',
          800: '#133e8f',
          900: '#122f6e'
        }
      },
      keyframes: {
        'fade-in': { '0%': { opacity: 0 }, '100%': { opacity: 1 } },
        'slide-up': {
          '0%': { transform: 'translateY(10px)', opacity: 0 },
          '100%': { transform: 'translateY(0)', opacity: 1 }
        }
      },
      animation: {
        'fade-in': 'fade-in 300ms ease-out',
        'slide-up': 'slide-up 300ms ease-out'
      }
    },
  },
  plugins: [typography],
}



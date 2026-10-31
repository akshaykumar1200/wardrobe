/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: '#F7F7F4',
        surface: '#FFFFFF',
        ink: {
          DEFAULT: '#1C1E1A',
          muted: '#6E7269',
        },
        line: '#E3E4DE',
        sage: {
          DEFAULT: '#7D8C71',
          deep: '#5C6B52',
          wash: '#EDF0EA',
        },
        danger: '#9C5B4E',
      },
      fontFamily: {
        display: ['Fraunces', 'Georgia', 'serif'],
        body: ['DM Sans', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'garment': '0 8px 16px rgba(28, 30, 26, 0.10)',
        'card': '0 4px 20px rgba(0, 0, 0, 0.03)',
        'modal': '0 20px 50px rgba(0, 0, 0, 0.12)',
      }
    },
  },
  plugins: [],
}

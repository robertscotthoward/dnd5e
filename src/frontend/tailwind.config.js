/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        cinzel: ['"Cinzel"', 'serif'],
        crimson: ['"Crimson Text"', 'serif'],
        sans: ['"Crimson Text"', 'serif'],
      },
      colors: {
        'dnd-dark': '#0d0a06',
        'dnd-surface': '#1a1109',
        'dnd-card': '#221608',
        'dnd-gold': '#c9a227',
        'dnd-gold-light': '#e8c84a',
        'dnd-parchment': '#e8d5b7',
        'dnd-muted': '#8a7355',
        'dnd-red': '#8b1a1a',
        'dnd-green': '#1a4a1a',
        'dnd-border': '#3d2e10',
      },
      boxShadow: {
        'gold': '0 0 12px rgba(201,162,39,0.3)',
        'gold-lg': '0 0 24px rgba(201,162,39,0.5)',
      },
    },
  },
  plugins: [],
}

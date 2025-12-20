/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        crypto: {
          dark: "#0b0e11",
          card: "#151a21",
          accent: "#2962ff",
          up: "#00c853",
          down: "#ff3d00",
          text: "#eaecef"
        }
      }
    },
  },
  plugins: [],
}

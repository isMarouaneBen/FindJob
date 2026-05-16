/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dbe6ff",
          500: "#3b6cff",
          600: "#2854f5",
          700: "#1f43cc",
        },
      },
    },
  },
  plugins: [],
};

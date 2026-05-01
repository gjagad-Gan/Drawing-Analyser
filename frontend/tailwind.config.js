/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        isc: {
          navy:  "#00205B",
          blue:  "#1F4E79",
          light: "#D6E4F0",
          orange:"#C55A11",
        },
      },
    },
  },
  plugins: [],
};

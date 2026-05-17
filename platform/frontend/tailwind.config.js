/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Geist"', '"Inter var"', "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ['"Geist"', '"Inter var"', "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ['"Geist Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      colors: {
        bg: {
          DEFAULT: "#0a0a0a",
          subtle:  "#0d0d0d",
          card:    "#111111",
          elevated:"#161616",
          hover:   "#1a1a1a",
        },
        line: {
          DEFAULT: "rgba(255,255,255,0.07)",
          subtle:  "rgba(255,255,255,0.04)",
          strong:  "rgba(255,255,255,0.12)",
          brand:   "rgba(99,102,241,0.35)",
        },
        text: {
          DEFAULT: "#fafafa",
          mute:    "rgba(255,255,255,0.62)",
          dim:     "rgba(255,255,255,0.45)",
          faint:   "rgba(255,255,255,0.28)",
        },
        brand: {
          50:  "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
        },
      },
      boxShadow: {
        soft:  "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 1px 2px rgba(0,0,0,0.4)",
        pop:   "0 8px 24px rgba(0,0,0,0.45)",
        glow:  "0 0 0 1px rgba(99,102,241,0.45), 0 0 32px -4px rgba(99,102,241,0.45)",
        ring:  "0 0 0 1px rgba(255,255,255,0.08)",
        "ring-strong": "0 0 0 1px rgba(255,255,255,0.18)",
      },
      backgroundImage: {
        "gradient-brand":
          "linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #ec4899 100%)",
        "gradient-text":
          "linear-gradient(180deg, #ffffff 0%, rgba(255,255,255,0.65) 100%)",
        "gradient-cta":
          "linear-gradient(180deg, #6366f1 0%, #4f46e5 100%)",
        "dot-grid":
          "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.07) 1px, transparent 0)",
        "line-grid":
          "linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px)",
        "noise": "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.35'/%3E%3C/svg%3E\")",
      },
      keyframes: {
        "fade-in":  { from: { opacity: 0 }, to: { opacity: 1 } },
        "fade-up":  { from: { opacity: 0, transform: "translateY(12px)" },
                      to:   { opacity: 1, transform: "translateY(0)" } },
        "scale-in": { from: { opacity: 0, transform: "scale(.96)" },
                      to:   { opacity: 1, transform: "scale(1)" } },
        shimmer:    { "0%":   { backgroundPosition: "-200% 0" },
                      "100%": { backgroundPosition: "200% 0" } },

        // Aurora orbs — slow, organic drift
        "aurora-1": {
          "0%, 100%": { transform: "translate3d(0,0,0) scale(1)" },
          "33%":      { transform: "translate3d(40px,-30px,0) scale(1.15)" },
          "66%":      { transform: "translate3d(-30px,30px,0) scale(0.92)" },
        },
        "aurora-2": {
          "0%, 100%": { transform: "translate3d(0,0,0) scale(1)" },
          "50%":      { transform: "translate3d(-60px,40px,0) scale(1.2)" },
        },
        "aurora-3": {
          "0%, 100%": { transform: "translate3d(0,0,0) scale(1)" },
          "40%":      { transform: "translate3d(30px,30px,0) scale(1.1)" },
          "80%":      { transform: "translate3d(-20px,-30px,0) scale(0.95)" },
        },
        // Soft pulse for indicator dots
        "pulse-soft": {
          "0%, 100%": { opacity: 0.5, transform: "scale(1)" },
          "50%":      { opacity: 1, transform: "scale(1.1)" },
        },
        // Marquee scroll for the logos line
        marquee: {
          "0%":   { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
        // Conic spin for animated borders
        "spin-slow": { to: { transform: "rotate(360deg)" } },
        // Beam scan
        beam: {
          "0%":   { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-in":  "fade-in 0.4s ease-out",
        "fade-up":  "fade-up 0.5s ease-out both",
        "scale-in": "scale-in 0.25s ease-out",
        shimmer:    "shimmer 1.6s linear infinite",
        "aurora-1": "aurora-1 22s ease-in-out infinite",
        "aurora-2": "aurora-2 30s ease-in-out infinite",
        "aurora-3": "aurora-3 26s ease-in-out infinite",
        "pulse-soft": "pulse-soft 2.5s ease-in-out infinite",
        marquee:    "marquee 30s linear infinite",
        "spin-slow":"spin-slow 8s linear infinite",
        beam:       "beam 2.5s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

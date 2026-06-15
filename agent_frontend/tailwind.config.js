/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Brand colors
        brand: {
          50:  "#edf7f0",
          100: "#d0ecd8",
          200: "#a3d9b3",
          300: "#6fc28d",
          400: "#3fa86a",
          500: "#1F7A3D",
          600: "#176332",
          700: "#124d27",
          800: "#0c371c",
          900: "#072112",
        },
        amber: {
          50:  "#fff8e6",
          100: "#ffefc2",
          500: "#9A6700",
          600: "#7d5300",
        }
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      keyframes: {
        "accordion-down": {
          from: { height: 0 },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: 0 },
        },
        "slide-in-right": {
          from: { transform: "translateX(100%)", opacity: 0 },
          to: { transform: "translateX(0)", opacity: 1 },
        },
        "fade-in": {
          from: { opacity: 0, transform: "translateY(8px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },
        "spin-slow": {
          to: { transform: "rotate(360deg)" },
        },
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(31, 122, 61, 0)" },
          "50%": { boxShadow: "0 0 0 6px rgba(31, 122, 61, 0.15)" },
        },
        "flash-border": {
          "0%": { boxShadow: "inset 0 0 0 2px rgba(31,122,61,0)" },
          "40%": { boxShadow: "inset 0 0 0 2px rgba(31,122,61,0.4)" },
          "100%": { boxShadow: "inset 0 0 0 2px rgba(31,122,61,0)" },
        },
        "bounce-in": {
          "0%": { transform: "scale(0.3)", opacity: 0 },
          "60%": { transform: "scale(1.08)" },
          "100%": { transform: "scale(1)", opacity: 1 },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "slide-in-right": "slide-in-right 0.3s ease-out",
        "fade-in": "fade-in 0.3s ease-out",
        "spin-slow": "spin-slow 0.8s linear infinite",
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "flash-border": "flash-border 0.8s ease-out",
        "bounce-in": "bounce-in 0.4s ease-out",
      },
      boxShadow: {
        "card": "0 1px 3px rgba(0,0,0,0.06), 0 4px 16px rgba(0,0,0,0.06)",
        "card-hover": "0 4px 12px rgba(0,0,0,0.1), 0 12px 32px rgba(0,0,0,0.08)",
        "chat": "0 2px 8px rgba(0,0,0,0.08)",
        "glow-green": "0 0 20px rgba(31, 122, 61, 0.3)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,html}"],
  theme: {
    extend: {
      /* ── Colors ─────────────────────────────────────── */
      colors: {
        primary: {
          DEFAULT: "#0E76E4",        // Blue — main brand, links, CTAs
          light: "#F3F7FC",          // Light blue — section backgrounds
          "light-2": "#E9F3FD",      // Deeper blue tint — hover/active
        },
        neutral: {
          white: "#FFFFFF",
          black: "#0B0B0B",          // Near-black — primary text
          sub: "#717191",            // Muted text / secondary labels
          border: "#BDBDCA",         // Input borders, card outlines
          line: "#DADADA",           // Dividers, separators
          "light-grey": "#FAF8F8",   // Surface background
        },
        attention: "#FB822C",        // Orange — warnings, highlights
      },

      /* ── Typography ─────────────────────────────────── */
      fontFamily: {
        heading: ["Inter", "sans-serif"],
        body: ["'IBM Plex Sans'", "sans-serif"],
        "mobile-heading": ["Montserrat", "sans-serif"],
      },
      fontSize: {
        // Desktop headings
        "big":  ["40px", { lineHeight: "120%", fontWeight: "500" }],
        "h1t":  ["48px", { lineHeight: "120%", fontWeight: "500" }],
        "h1":   ["32px", { lineHeight: "150%", fontWeight: "500" }],
        "h1b":  ["32px", { lineHeight: "130%", fontWeight: "700" }],
        "h2":   ["24px", { lineHeight: "150%", fontWeight: "400" }],
        "h2m":  ["24px", { lineHeight: "150%", fontWeight: "500" }],
        "h3":   ["20px", { lineHeight: "120%", fontWeight: "700" }],
        "h3m":  ["20px", { lineHeight: "120%", fontWeight: "500" }],
        "h4":   ["18px", { lineHeight: "120%", fontWeight: "500" }],
        "h5":   ["16px", { lineHeight: "120%", fontWeight: "500" }],
        "h6":   ["14px", { lineHeight: "140%", fontWeight: "700" }],
        "h7":   ["12px", { lineHeight: "120%", fontWeight: "400" }],
        // Body
        "body-1":  ["24px", { lineHeight: "150%", fontWeight: "400" }],
        "body-2":  ["16px", { lineHeight: "150%", fontWeight: "400" }],
        "body-2m": ["16px", { lineHeight: "150%", fontWeight: "500" }],
        "body-2b": ["16px", { lineHeight: "150%", fontWeight: "700" }],
        "body-3":  ["14px", { lineHeight: "140%", fontWeight: "400" }],
        "body-3m": ["14px", { lineHeight: "140%", fontWeight: "500" }],
        "body-4":  ["12px", { lineHeight: "120%", fontWeight: "500" }],
        "body-4r": ["12px", { lineHeight: "120%", fontWeight: "400" }],
        // Button
        "btn-1":  ["18px", { lineHeight: "150%", fontWeight: "600" }],
        "btn-2":  ["16px", { lineHeight: "150%", fontWeight: "400" }],
        "btn-3":  ["14px", { lineHeight: "140%", fontWeight: "500" }],
        "btn-3b": ["14px", { lineHeight: "140%", fontWeight: "600" }],
        "btn-4":  ["12px", { lineHeight: "120%", fontWeight: "500" }],
      },

      /* ── Spacing (4px base grid) ────────────────────── */
      spacing: {
        "0.5": "2px",
        "1":   "4px",
        "1.5": "6px",
        "2":   "8px",
        "2.5": "10px",
        "3":   "12px",
        "4":   "16px",
        "5":   "20px",
        "6":   "24px",
        "8":   "32px",
        "9":   "35px",
        "12":  "48px",
        "16":  "64px",
        "20":  "80px",
      },

      /* ── Border Radius ──────────────────────────────── */
      borderRadius: {
        sm:      "4px",
        DEFAULT: "6px",
        md:      "8px",
        lg:      "14px",
        xl:      "18px",
        "2xl":   "24px",
        "3xl":   "28px",
        pill:    "60px",
        full:    "80px",
      },

      /* ── Shadows (disabled — flat design, no elevation) */
      boxShadow: {
        none: "none",
      },
    },
  },
  plugins: [],
};

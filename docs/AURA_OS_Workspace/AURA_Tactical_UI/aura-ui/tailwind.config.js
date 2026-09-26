/** @type {import('tailwindcss').Config} */
export default {
    content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
    theme: {
        extend: {
            colors: {
                aura: {
                    bg: "#0b0f14",
                    panel: "#0f141b",
                    cyan: "#00f0ff",
                    blue: "#2266ff",
                    green: "#33ff99",
                    purple: "#b066ff",
                    muted: "#6b7280",
                },
            },
            boxShadow: {
                glow: "0 0 20px rgba(0,240,255,0.25)",
                "glow-strong": "0 0 40px rgba(0,240,255,0.45)",
            },
            borderRadius: {
                lg: "12px",
                xl: "16px",
            },
        },
    },
    plugins: [],
};

/** @type {import('next').NextConfig} */
// Config dedicada al build nativo Android vía Capacitor.
// `output: 'export'` genera sitio estático que Capacitor sirve desde assets.
const base = require("./next.config.js");

const androidConfig = {
  ...base,
  output: "export",
  // En Capacitor los assets se sirven desde file://; las rutas deben ser relativas.
  basePath: "",
  assetPrefix: "./",
  images: {
    unoptimized: true, // evita el optimizador de imágenes de Next (no disponible en export)
  },
  trailingSlash: true,
  env: {
    ...(base.env || {}),
    NEXT_PUBLIC_IS_NATIVE: "1",
  },
};

module.exports = androidConfig;
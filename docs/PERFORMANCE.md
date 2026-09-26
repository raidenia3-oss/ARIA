# Performance Metrics — AURA/AME v3.0

> ⚠️ Los scores de Lighthouse **no se miden en este entorno** (requiere Chrome
> + un servidor vivo contra la URL de producción de Vercel). Ejecuta Lighthouse
> tú mismo contra `https://aura-web-chi-seven.vercel.app` para obtener números
> reales. Esta guía documenta las optimizaciones aplicadas y cómo medir.

## Cómo medir (Lighthouse)

```bash
# Localmente contra un despliegue de Vercel (no contra next dev):
npx lighthouse https://aura-web-chi-seven.vercel.app --view

# O como CI (ej. en GitHub Actions), exportando JSON:
npx lighthouse https://aura-web-chi-seven.vercel.app \
  --output=json --output-path=./lighthouse.json
```

Objetivo de la v3.0: **Performance / Accessibility / Best Practices / SEO ≥ 90**.

## Core Web Vitals (objetivo)

- **LCP** (Largest Contentful Paint): < 2.5s
- **FID** / **INP** (First Input Delay / Interaction to Next Paint): < 100ms
- **CLS** (Cumulative Layout Shift): < 0.1

## Optimizaciones aplicadas en v3.0

- ✅ **Code splitting** automático por ruta (Next.js App Router).
- ✅ **Cero dependencias nuevas** en v3.0: el dashboard de analytics usa
  gráficos de barras con CSS/SVG sin librería de charts.
- ✅ **Estilos inline** basados en la paleta AURA (`components/palette.ts`),
  sin framework CSS pesado en runtime.
- ✅ **Funciones serverless pequeñas** (`route.ts`) con lógica mínima.
- ✅ **Retry con backoff** (`lib/fetch-retry.ts`) para no bloquear la UI.

## Bundle

El tamaño exacto depende del build de Vercel (`next build`). Para inspeccionar:

```bash
cd frontend
npm run build
# Revisa .next/ con next-shield o el reporte de build de Vercel
```

## Known Issues

- ⚠️ **Rate limiting** solo está en `ame-core`; las rutas de integraciones aún
  no lo aplican (ver `MEJORAS-FASE-57.md`). No es crítico para v3.0 web.
- ⚠️ No hay service worker de caché avanzado en la app web (el PWA offline
  avanzado es trabajo de la Fase 58).

## Future Optimizations (Fase 58)

- Service Worker / caching strategy avanzado.
- Image CDN / optimización de imágenes.
- Persistencia (KV/Redis) para reducir cálculo por request.
- Analytics engine con agregación en backend (ver `setup-phase-58.md`).

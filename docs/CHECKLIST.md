# v3.0 Final Checklist — Before Each Release

> Lista de verificación para releases. Los comandos de verificación local son
> `npm run typecheck`, `npm run lint:local` y `npm test` (el `lint`/`tsc`
> estándar falla por la versión de `next` en este entorno).

## Pre-Release Checklist

### Code Quality
- [ ] `npm run typecheck` → 0 errores
- [ ] `npm run lint:local` → 0 errores
- [ ] `npm test` → todos pasando
- [ ] Sin `console.log` en código de producción
- [ ] Sin `any` innecesarios en TypeScript
- [ ] Sin secrets hardcodeados

### Security
- [ ] Auth en `/api/webhooks` y `/api/logs` (bearer `API_SECRET_KEY`)
- [ ] CORS configurado en `next.config.js`
- [ ] Validación SSRF en `/api/webhooks`
- [ ] Sin vectores de inyección en inputs
- [ ] Dependencias al día (`npm audit`)
- [ ] Variables de entorno documentadas (`.env.example`)

### Documentation
- [ ] `README.md` actualizado
- [ ] `CHANGELOG.md` actualizado
- [ ] Ejemplos funcionales (`EXAMPLES.md`)
- [ ] API docs completas
- [ ] Setup guide al día (`setup-phase-58.md`)
- [ ] `TROUBLESHOOTING.md` cubre issues conocidos

### Testing
- [ ] Unit tests pasando
- [ ] Manual testing en localhost
- [ ] Probado en navegador móvil
- [ ] Probado en red lenta (DevTools throttling)

### Performance
- [ ] Lighthouse ≥ 90 (medir contra la URL de producción; ver `PERFORMANCE.md`)
- [ ] Tamaño de bundle razonable
- [ ] Response time de API < 500ms
- [ ] Sin memory leaks (DevTools)

### Deployment
- [ ] Preview URL de Vercel probado
- [ ] Variables de entorno configuradas
- [ ] Monitoreo 24/7 activo (`scripts/monitor-24-7.js`)

## Release Checklist

### Before Tagging
- [ ] Todos los ítems de arriba: ✓
- [ ] Mensaje de commit claro
- [ ] Branch mergeada a `main`
- [ ] Tests pasando

### Create Release
- [ ] Tag: `git tag -a vX.Y.Z -m "..."`
- [ ] Push tag: `git push origin vX.Y.Z`
- [ ] Crear GitHub Release con notas
- [ ] Actualizar documentación

### Post-Release
- [ ] Monitorear `/api/logs` por errores
- [ ] Revisar dashboard de analytics
- [ ] Verificar integraciones funcionando

## Phase 58 Pre-Implementation Checklist (para Cline)

- [ ] Python venv listo (`source venv/bin/activate`)
- [ ] `.env.local` configurado con todas las vars
- [ ] `requirements.txt` instalado
- [ ] `setup-phase-58.md` leído completamente
- [ ] GitHub issues creadas por opción (A/D/F)
- [ ] Firebase project creado (mobile)
- [ ] HuggingFace account listo (fine-tuning)
- [ ] Cloud storage/DB configurado (analytics)

# Contributing to AURA/AME

¡Gracias por tu interés en contribuir a AURA/AME! Este documento proporciona las pautas para contribuir al proyecto.

## 📋 Índice

1. [Código de Conducta](#código-de-conducta)
2. [Cómo Empezar](#cómo-empezar)
3. [Flujo de Trabajo](#flujo-de-trabajo)
4. [Estándares de Código](#estándares-de-código)
5. [Pruebas](#pruebas)
6. [Documentación](#documentación)
7. [Reportar Issues](#reportar-issues)

## Código de Conducta

Este proyecto sigue un [Código de Conducta](CODE_OF_CONDUCT.md). Al participar, se espera que mantengas este código.

## Cómo Empezar

1. **Fork el repositorio**
2. **Clona tu fork:**
   ```bash
   git clone https://github.com/tu-usuario/AURA-server.01.git
   cd AURA-server.01
   ```
3. **Instala dependencias:**
   ```bash
   cd frontend
   npm install
   ```
4. **Crea una rama:**
   ```bash
   git checkout -b feature/tu-feature
   ```

## Flujo de Trabajo

1. **Asegúrate de estar en `main` actualizado:**
   ```bash
   git checkout main
   git pull origin main
   ```
2. **Crea una rama descriptiva:**
   - `feature/` para nuevas características
   - `fix/` para correcciones
   - `docs/` para documentación
   - `refactor/` para refactorización

3. **Haz commits pequeños y descriptivos:**

   ```bash
   git commit -m "feat: agregar sistema de notificaciones push"
   ```

4. **Push a tu fork y abre un Pull Request**

## Estándares de Código

### JavaScript/React

- Usa `const` y `let`, nunca `var`
- Sigue el estilo de Prettier (archivo `.prettierrc` incluido)
- Componentes en PascalCase
- Funciones en camelCase
- Constantes en UPPER_SNAKE_CASE

### Python

- Sigue PEP 8
- Usa type hints
- Docstrings en formato Google

### Commits

Usa [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` nueva característica
- `fix:` corrección de bug
- `docs:` cambios en documentación
- `refactor:` refactorización
- `test:` agregar o modificar tests
- `chore:` tareas de mantenimiento

## Pruebas

- Ejecuta tests antes de hacer commit:
  ```bash
  cd frontend && npm test
  ```
- Agrega tests para nuevas funcionalidades
- Mantén cobertura de código > 80%

## Verificación local (antes de PR)

El entorno fija `next` en una versión antigua, así que los comandos estándar
`npm run lint` / `tsc` fallan. Usa los scripts locales:

```bash
cd frontend
npm run typecheck   # tsc -p tsconfig.local.json --noEmit
npm run lint:local  # eslint -c eslint.local.mjs .
npm test            # node --test
```

## Seguridad

- **Nunca** hagas commit de API keys ni secrets (usa `.env.local`).
- Valida siempre los inputs, especialmente URLs externas (ver SSRF guard en
  `app/api/webhooks/route.ts`).
- Usa `authenticate` / `requireAuth` en cualquier API sensible.
- Aplica rate limiting a funciones costosas (ver `lib/rateLimit.ts`).

## Documentación

- Actualiza `README.md` si agregas funcionalidades
- Documenta APIs en `docs/`
- Agrega JSDoc para funciones públicas
- Mantén `CHANGELOG.md` actualizado

## Reportar Issues

Usa las plantillas de issues:

- **Bug Report**: Para reportar errores
- **Feature Request**: Para sugerir características
- **Documentation**: Para mejoras en documentación

Incluye siempre:

- Versión del proyecto
- Sistema operativo
- Pasos para reproducir (para bugs)
- Logs relevantes

---

¡Gracias por contribuir! 🚀

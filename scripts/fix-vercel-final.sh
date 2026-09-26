#!/bin/bash

echo "🔧 FIX FINAL Vercel"

cd frontend

# 1. Eliminar TODOS los archivos Python
echo "1️⃣ Eliminando archivos Python..."
find . -name "*.py" -type f -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -type f -delete

# 2. Limpiar node_modules y cache
echo "2️⃣ Limpiando cache..."
rm -rf node_modules/.cache
rm -rf .next
rm -rf node_modules

# 3. Reinstalar dependencias
echo "3️⃣ Reinstalando dependencias..."
npm install

# 4. Verificar que build funcione
echo "4️⃣ Testeando build local..."
npm run build

if [ $? -eq 0 ]; then
    echo "✅ Build local OK"
else
    echo "❌ Build local falló"
    exit 1
fi

# 5. Limpiar archivos de versioning
echo "5️⃣ Limpiando git..."
git add -A
git commit -m "Fix: Remove Python files, clean cache, fix Vercel"

# 6. Deploy
echo "6️⃣ Deployando a Vercel..."
vercel deploy --prod --force

echo "✅ Vercel deployment completado"
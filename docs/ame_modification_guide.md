# Guía de Modificación AME sin Root

## Herramientas necesarias

- **MT Manager** ( Explorador APK)
- **APK Editor Studio** (alternativa)
- **ADB** (Android Debug Bridge)
- **7-Zip** (para descomprimir)

## Modificaciones posibles

### 1. Cambiar recursos visuales

```
Pasos:
1. Abrir APK con MT Manager
2. Navegar a /res/drawable-*
3. Reemplazar iconos (mismo nombre, nueva imagen)
4. Guardar y firmar APK
```

### 2. Modificar strings.xml

```
1. En MT Manager: /res/values/strings.xml
2. Editar textos visibles
3. Mantener longitud similar para evitar crashes
```

### 3. Instalar módulos extra con ADB

```bash
adb install modificacion_ame.apk
adb shell pm grant com.aura.mobile android.permission.SYSTEM_ALERT_WINDOW
```

## Limitaciones sin root

- No se pueden modificar archivos del sistema
- No se puede cambiar la firma de la app
- Algunos módulos requieren acceso root

## Backup

Siempre hacer backup del APK original antes de modificar.

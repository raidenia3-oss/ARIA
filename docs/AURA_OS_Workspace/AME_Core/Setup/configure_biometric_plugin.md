# Configuración del Plugin Biométrico para AURA

## Requisitos Previos
- Node.js y npm instalados.
- Capacitor CLI instalado (`npm install -g @capacitor/cli`).
- Android Studio configurado para desarrollo de aplicaciones Android.

## Pasos para Configurar el Plugin

### 1. Instalar el Plugin Biométrico
Ejecuta el siguiente comando en la raíz del proyecto para instalar el plugin `@capacitor-community/biometric-auth`:

```bash
npm install @capacitor-community/biometric-auth
```

### 2. Añadir el Plugin a Capacitor
Asegúrate de que el plugin esté configurado en `capacitor.config.ts` como se muestra a continuación:

```typescript
plugins: {
  // ... otros plugins ...
  BiometricAuth: {
    install: 'node_modules/@capacitor-community/biometric-auth',
    config: {
      android: {
        fingerprint: {
          enabled: true,
          title: 'Autenticación con Huella',
          subtitle: 'Coloque su dedo en el sensor',
          description: 'Autenticación biométrica segura',
          cancelLabel: 'Cancelar',
          fallbackLabel: 'Usar contraseña'
        },
        face: {
          enabled: true,
          title: 'Autenticación Facial',
          subtitle: 'Mire a la cámara',
          description: 'Autenticación biométrica segura',
          cancelLabel: 'Cancelar',
          fallbackLabel: 'Usar contraseña'
        }
      }
    }
  }
}
```

### 3. Sincronizar el Plugin con Capacitor
Ejecuta el siguiente comando para sincronizar el plugin con Capacitor:

```bash
npx cap sync
```

### 4. Configurar Permisos en Android
Asegúrate de que los permisos necesarios estén configurados en el `AndroidManifest.xml` del proyecto. Los permisos necesarios ya están incluidos en la configuración de `Permissions` en `capacitor.config.ts`.

### 5. Probar la Autenticación Biométrica
Para probar la autenticación biométrica, ejecuta la aplicación en un dispositivo Android con soporte para biometría (huella dactilar o reconocimiento facial).

### 6. Configurar el Backend
Asegúrate de que el backend en `Shadow-Core` esté corriendo y configurado para manejar las solicitudes de autenticación biométrica. El módulo `biometric_auth.py` ya está implementado y listo para uso.

### 7. Flujo de Autenticación
El flujo de autenticación está implementado en `biometricAuth.js` y sigue estos pasos:
1. Al abrir la app, se solicita autenticación biométrica.
2. Si la autenticación es exitosa, se obtiene un token JWT del backend.
3. El token se almacena de forma segura y se incluye en las cabeceras de todas las peticiones HTTP.

## Solución de Problemas

### Error: Plugin no disponible
Si recibes un error indicando que el plugin no está disponible, asegúrate de que:
- El plugin esté correctamente instalado (`npm install @capacitor-community/biometric-auth`).
- El plugin esté sincronizado con Capacitor (`npx cap sync`).
- El dispositivo tenga soporte para biometría.

### Error: Permisos no concedidos
Si la aplicación no puede acceder a los sensores biométricos, verifica que:
- Los permisos necesarios estén configurados en `AndroidManifest.xml`.
- El usuario haya concedido los permisos necesarios en el dispositivo.

## Notas Adicionales
- Este plugin soporta tanto autenticación por huella dactilar como por reconocimiento facial.
- Asegúrate de que el dispositivo tenga configurada una forma de autenticación biométrica (huella dactilar o Face ID).
- Para entornos de producción, considera usar un almacenamiento más seguro para el token JWT, como `SecureStorage` de Capacitor.
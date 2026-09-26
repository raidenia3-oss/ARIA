# Manual de Compilación para AURA Mobile (Android APK)

## Requisitos Previos

Para compilar la aplicación móvil de AURA, necesitas instalar las siguientes herramientas en tu sistema:

### 1. Java Development Kit (JDK)

- **Versión Recomendada:** JDK 11 o superior
- **Descarga:** [Oracle JDK](https://www.oracle.com/java/technologies/javase-jdk11-downloads.html) o [OpenJDK](https://adoptium.net/)

### 2. Android Studio

- **Versión Recomendada:** Android Studio 4.2 o superior
- **Descarga:** [Android Studio](https://developer.android.com/studio)

### 3. Gradle

- **Versión Recomendada:** Gradle 7.4 o superior
- **Instalación:** Se instala automáticamente con Android Studio, pero puedes verificar su versión con:
  ```bash
  gradle -v
  ```

### 4. Android SDK y Herramientas de Plataforma

- **Componentes Necesarios:**
  - Android SDK Platform 33
  - Android SDK Build-Tools 33.0.0
  - Android Emulator (opcional, para pruebas)

---

## Instrucciones de Instalación

### Instalar Java JDK

1. Descarga e instala el JDK.
2. Asegúrate de que la variable de entorno `JAVA_HOME` esté configurada correctamente.
3. Verifica la instalación:
   ```bash
   java -version
   ```

### Instalar Android Studio

1. Descarga e instala Android Studio.
2. Durante la instalación, selecciona las siguientes opciones:
   - Android SDK
   - Android SDK Platform 33
   - Android SDK Build-Tools 33.0.0
   - Android Emulator (opcional)

3. Abre Android Studio y completa la configuración inicial:
   - Selecciona un tema y tipo de configuración.
   - Descarga las actualizaciones disponibles.

4. Verifica la instalación:
   - Abre la terminal integrada de Android Studio y ejecuta:
     ```bash
     sdkmanager --list
     ```

---

## Configuración del Entorno

### Configurar Variables de Entorno

Agrega las siguientes variables de entorno en tu sistema operativo:

- **Windows:**
  - `ANDROID_HOME`: Ruta donde está instalado el SDK de Android (ejemplo: `C:\Users\<tu_usuario>\AppData\Local\Android\Sdk`)
  - `PATH`: Añade `%ANDROID_HOME%\platform-tools`, `%ANDROID_HOME%\tools`, y `%ANDROID_HOME%\tools\bin`

- **Linux/macOS:**
  - `ANDROID_HOME`: Ruta del SDK de Android (ejemplo: `~/Android/Sdk`)
  - `PATH`: Añade `$ANDROID_HOME/platform-tools`, `$ANDROID_HOME/tools`, y `$ANDROID_HOME/tools/bin`

### Verificar Variables de Entorno

Ejecuta los siguientes comandos para verificar que las variables estén configuradas correctamente:

```bash
echo $ANDROID_HOME
echo $JAVA_HOME
```

---

## Compilación de la APK

### Usando Android Studio

1. Abre Android Studio.
2. Selecciona **File > Open** y navega hasta la carpeta `AME_EXPORT_PACKAGE/ANDROID_APP`.
3. Espera a que Android Studio sincronice los archivos del proyecto.
4. Una vez sincronizado, selecciona **Build > Build Bundle(s) / APK(s) > Build APK**.
5. Android Studio generará la APK en la ruta:
   ```
   AME_EXPORT_PACKAGE/ANDROID_APP/app/build/outputs/apk/release/app-release.apk
   ```

### Usando Línea de Comandos

1. Navega hasta la carpeta del proyecto:

   ```bash
   cd AME_EXPORT_PACKAGE/ANDROID_APP
   ```

2. Ejecuta el siguiente comando para compilar la APK:

   ```bash
   ./gradlew assembleRelease
   ```

3. La APK generada se encontrará en:
   ```
   AME_EXPORT_PACKAGE/ANDROID_APP/app/build/outputs/apk/release/app-release.apk
   ```

---

## Solución de Problemas

### Error: "Failed to find target with hash string 'android-33'"

- Asegúrate de que el SDK de Android esté instalado correctamente.
- Ejecuta el siguiente comando para instalar la plataforma necesaria:
  ```bash
  sdkmanager "platforms;android-33"
  ```

### Error: "Could not find com.android.tools.build:gradle:7.4.0"

- Asegúrate de que Gradle esté instalado.
- Ejecuta el siguiente comando para sincronizar los plugins de Gradle:
  ```bash
  sdkmanager "platform-tools" "build-tools;33.0.0"
  ```

### Error: "Java version is not supported"

- Asegúrate de que estés usando Java 11 o superior.
- Cambia la versión de Java en el archivo `build.gradle` si es necesario.

---

## Transferencia de la APK al Dispositivo Móvil

Una vez compilada la APK, puedes transferirla a tu dispositivo móvil de varias formas:

1. **Usando ADB (Android Debug Bridge):**

   ```bash
   adb install app-release.apk
   ```

2. **Transferencia Manual:**
   - Conecta tu dispositivo móvil a la computadora.
   - Copia el archivo `app-release.apk` a la memoria interna o externa de tu dispositivo.
   - Abre el archivo APK en tu dispositivo para instalarlo.

---

## Notas Adicionales

- **Configuración de Capacitor:** Asegúrate de que el archivo `capacitor.config.ts` esté correctamente configurado para conectarse al servidor de AURA.
- **Endpoints:** Verifica que la URL en `capacitor.config.ts` apunte al servidor correcto:

  ```typescript
  server: {
    androidScheme: 'https',
    url: 'https://tu-tunel-cloudflare.com', // Cambia esto por la URL de tu servidor
    cleartext: true
  }
  ```

- **Pruebas:** Antes de enviar la APK, prueba la aplicación en un emulador o dispositivo físico para asegurarte de que todo funcione correctamente.

---

## Resumen de Comandos Útiles

| Comando                             | Descripción                                     |
| ----------------------------------- | ----------------------------------------------- |
| `sdkmanager --list`                 | Lista las herramientas y plataformas instaladas |
| `sdkmanager "platforms;android-33"` | Instala la plataforma Android 33                |
| `sdkmanager "build-tools;33.0.0"`   | Instala las herramientas de construcción 33.0.0 |
| `./gradlew clean`                   | Limpia el proyecto antes de compilar            |
| `./gradlew assembleRelease`         | Compila la APK en modo release                  |
| `adb devices`                       | Lista los dispositivos conectados               |
| `adb install app-release.apk`       | Instala la APK en un dispositivo conectado      |

---

## Contacto y Soporte

Si encuentras algún problema durante la compilación, revisa los logs generados y consulta la documentación oficial de Android Studio y Gradle. Para soporte adicional, contacta al equipo de desarrollo de AURA.

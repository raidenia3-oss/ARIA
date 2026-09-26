# Módulo Keylogger Táctico

Este documento describe el módulo **Keylogger Táctico** integrado en el ecosistema AURA/AME, diseñado para registrar pulsaciones de teclado en dispositivos móviles con fines de auditoría y seguridad.

## ⚠️ Advertencia Importante

**Este módulo debe usarse únicamente en dispositivos que sean propiedad del usuario y con su consentimiento explícito.** El uso no autorizado de keyloggers puede ser ilegal y violar leyes de privacidad como GDPR, CCPA, y otras regulaciones locales e internacionales.

## 🔧 Funcionalidades Principales

### 1. Registro de Teclas

El módulo registra las pulsaciones de teclado en tiempo real.

- **Tipos de eventos registrados**:
  - Teclas presionadas
  - Teclas liberadas
  - Combinaciones de teclas
  - Eventos de teclado especiales (Ctrl, Alt, Shift, etc.)

### 2. Almacenamiento Seguro

Los datos registrados se almacenan de manera segura en el dispositivo.

- **Formato de almacenamiento**:
  - Archivos cifrados en la memoria interna del dispositivo.
  - Base de datos local encriptada.
  - Buffer en memoria para eventos recientes.

### 3. Sincronización con el Servidor Central

Los datos registrados pueden sincronizarse con el servidor central para análisis posterior.

- **Mecanismo de sincronización**:
  - Envío periódico de datos al servidor central.
  - Sincronización en tiempo real mediante WebSockets.
  - Compresión y cifrado de datos antes del envío.

### 4. Configuración de Filtros

El módulo permite configurar filtros para registrar solo eventos específicos.

- **Tipos de filtros**:
  - Filtro por aplicaciones (solo registrar en ciertas apps).
  - Filtro por tipo de teclas (solo letras, solo números, etc.).
  - Filtro por intervalos de tiempo (solo registrar en ciertos horarios).

## 🛠 Configuración

### 1. Configuración en el Agente de Termux

El módulo Keylogger Táctico se configura en el archivo `ame_config_template.json` del agente de Termux:

```json
{
  "keylogger": {
    "enabled": false, // Debe mantenerse desactivado por defecto
    "storage": {
      "path": "/sdcard/ame_keylogger",
      "max_size": 10485760, // 10MB máximo
      "encryption": true
    },
    "sync": {
      "interval": 3600, // Sincronización cada hora
      "server_url": "http://192.168.1.100:8000/v1/keylogger",
      "compression": true
    },
    "filters": {
      "apps": ["com.termux", "com.android.chrome"],
      "keys": ["letters", "numbers"],
      "time_ranges": [{ "start": "09:00", "end": "17:00" }]
    }
  }
}
```

### 2. Configuración en las Apps Móviles

Las aplicaciones móviles pueden configurar parámetros del keylogger mediante la interfaz de usuario o archivos de configuración.

#### Ejemplo de configuración en APK AME:

```json
{
  "keylogger": {
    "default_settings": {
      "enabled": false,
      "storage_path": "/sdcard/ame_keylogger",
      "sync_interval": 3600,
      "max_storage_size": 10485760
    },
    "security": {
      "encryption_required": true,
      "authentication_required": true
    }
  }
}
```

## 🔄 Activación y Uso

### 1. Activación desde el Agente de Termux

El keylogger debe activarse manualmente desde el agente de Termux:

```bash
# Activar el keylogger (solo para uso autorizado)
python modules/wifi_client_telemetry.py --enable-keylogger

# Verificar estado
python modules/wifi_client_telemetry.py --keylogger-status

# Desactivar el keylogger
python modules/wifi_client_telemetry.py --disable-keylogger
```

### 2. Activación desde las Apps Móviles

Las aplicaciones móviles proporcionan una interfaz gráfica para activar y configurar el keylogger:

1. Abre la aplicación APK AME o App Maid.
2. Ve a la sección de "Módulos Tácticos".
3. Selecciona "Keylogger Táctico".
4. **Autenticación**: Ingresa credenciales de autenticación (si está configurado).
5. **Configuración**: Configura los parámetros del keylogger.
6. **Activación**: Activa el keylogger con confirmación de responsabilidad legal.
7. **Monitoreo**: Visualiza los datos registrados en tiempo real (si está configurado).

## 📌 Ejemplos de Comandos

### 1. Activar el Keylogger

```bash
python modules/wifi_client_telemetry.py --enable-keylogger --storage-path /sdcard/ame_keylogger
```

### 2. Verificar Estado del Keylogger

```bash
python modules/wifi_client_telemetry.py --keylogger-status
```

### 3. Desactivar el Keylogger

```bash
python modules/wifi_client_telemetry.py --disable-keylogger
```

### 4. Exportar Datos Registrados

```bash
python modules/wifi_client_telemetry.py --export-keylogger --output /sdcard/keylog_export.json
```

## 📊 Visualización de Resultados

Los datos registrados por el keylogger pueden visualizarse en:

1. **Consola de Termux**: Los eventos recientes se muestran en la terminal cuando se solicita.
2. **Apps Móviles**: Los datos se muestran en una interfaz segura con autenticación.
3. **Servidor Central**: Los datos sincronizados se almacenan en el buffer del servidor central y pueden consultarse mediante la API (con autenticación adecuada).

## 🔒 Seguridad y Protección de Datos

### 1. Autenticación Requerida

El acceso al keylogger y a los datos registrados requiere autenticación:

- **Autenticación biométrica**: En las apps móviles.
- **Autenticación por contraseña**: Para acceso remoto a los datos.
- **Autenticación de dos factores**: Recomendado para entornos sensibles.

### 2. Cifrado de Datos

Todos los datos registrados están cifrados:

- **Cifrado en tránsito**: HTTPS/TLS para comunicación con el servidor.
- **Cifrado en reposo**: AES-256 para archivos de almacenamiento.
- **Cifrado de clave**: Claves almacenadas en el sistema de seguridad del dispositivo.

### 3. Gestión de Claves

Las claves de cifrado se gestionan de la siguiente manera:

- **Claves maestras**: Almacenadas en el sistema de seguridad del dispositivo.
- **Claves de sesión**: Generadas dinámicamente para cada sesión.
- **Rotación de claves**: Periódica para mantener la seguridad.

## 📌 Notas Importantes

- **Uso ético y legal**: Este módulo **solo debe usarse en dispositivos propiedad del usuario y con su consentimiento explícito**.
- **Responsabilidad legal**: El usuario es responsable del uso adecuado de este módulo y de cumplir con todas las leyes aplicables.
- **Enlaces internos**: Utiliza el formato `[[Archivo]]` para mantener la integridad del grafo de Obsidian.
- **Documentación**: Mantén un registro detallado de cuándo y por qué se activó el keylogger.
- **Alternativas**: Considera usar métodos menos intrusivos para auditoría de seguridad, como registros de actividad del sistema o análisis de tráfico de red.

## 📝 Ejemplo de Uso Autorizado

1. **Configuración Inicial**:
   - Configura el módulo en `ame_config_template.json` del agente de Termux.
   - Establece parámetros de seguridad (cifrado, autenticación).
   - Configura filtros para registrar solo eventos relevantes.

2. **Obtención de Consentimiento**:
   - Obtén consentimiento explícito del usuario del dispositivo.
   - Documenta el consentimiento y los términos de uso.

3. **Activación**:
   - Activa el keylogger solo cuando sea necesario:
     ```bash
     python modules/wifi_client_telemetry.py --enable-keylogger
     ```
   - Monitorea el estado del keylogger regularmente.

4. **Recolección de Datos**:
   - Revisa los datos registrados periódicamente.
   - Exporta los datos para análisis cuando sea necesario:
     ```bash
     python modules/wifi_client_telemetry.py --export-keylogger --output /sdcard/keylog_analysis.json
     ```

5. **Desactivación**:
   - Desactiva el keylogger cuando ya no sea necesario:
     ```bash
     python modules/wifi_client_telemetry.py --disable-keylogger
     ```
   - Elimina los datos registrados si ya no son necesarios.

6. **Análisis**:
   - Analiza los datos en un entorno seguro y con las protecciones adecuadas.
   - No compartas los datos con terceros sin el consentimiento explícito del usuario.

## 📌 Solución de Problemas

### 1. Errores de Permisos

- Asegúrate de que el agente de Termux tenga los permisos necesarios.
- Ejecuta `termux-setup-storage` para configurar el acceso a almacenamiento.
- Verifica que el dispositivo tenga permisos de administrador si es necesario.

### 2. Problemas de Conexión al Servidor

- Verifica que la URL del servidor en la configuración sea correcta.
- Asegúrate de que el servidor central esté en ejecución y accesible.
- Verifica que no haya firewalls bloqueando la comunicación.

### 3. Datos No Registrados

- Verifica que el keylogger esté activado.
- Asegúrate de que los filtros de configuración no estén bloqueando eventos.
- Prueba con aplicaciones específicas para verificar el registro.

### 4. Problemas de Almacenamiento

- Verifica que haya suficiente espacio en el almacenamiento configurado.
- Asegúrate de que el directorio de almacenamiento tenga permisos de escritura.
- Revisa los logs para identificar errores de almacenamiento.

## 🔗 Enlaces Relacionados

- [[01_Arquitectura/03_Nodo_Termux]]
- [[03_Módulos_Tácticos/01_Nmap_Advanced]]
- [[03_Módulos_Tácticos/02_OSINT_Sherlock]]

## 📌 Consideraciones Éticas y Legales

- **Consentimiento Informado**: Siempre obtén consentimiento informado y por escrito antes de usar este módulo.
- **Transparencia**: Sé transparente con el usuario sobre el uso del keylogger.
- **Duración**: Limita la duración de la recolección de datos al mínimo necesario.
- **Eliminación de Datos**: Elimina los datos registrados cuando ya no sean necesarios.
- **Protección de Datos**: Implementa todas las medidas de seguridad para proteger los datos registrados.

## 📝 Documentación de Uso

Mantén un registro detallado de cada uso del keylogger, incluyendo:

1. **Fecha y hora** de activación y desactivación.
2. **Dispositivo** en el que se usó.
3. **Usuario** que proporcionó el consentimiento.
4. **Objetivo** del uso (auditoría, investigación, etc.).
5. **Datos recolectados** (resumen, no datos sensibles).
6. **Acciones tomadas** con base en los datos recolectados.
7. **Eliminación de datos** (fecha y método).

Este registro debe almacenarse de manera segura y estar disponible para auditorías.

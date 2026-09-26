# Módulo Nmap Avanzado

Este documento describe el módulo **Nmap Avanzado** integrado en el ecosistema AURA/AME, que permite realizar escaneos avanzados de redes y hosts desde el agente de Termux y las aplicaciones móviles.

## 🔧 Funcionalidades Principales

### 1. Escaneo de Puertos Avanzado

El módulo permite realizar escaneos de puertos con diferentes técnicas y niveles de profundidad.

- **Tipos de escaneo**:
  - Escaneo TCP SYN (stealth scan)
  - Escaneo TCP Connect
  - Escaneo UDP
  - Escaneo de servicios (versión y OS detection)

- **Opciones avanzadas**:
  - Escaneo de puertos personalizados
  - Escaneo de puertos específicos
  - Escaneo de puertos en rangos
  - Escaneo de puertos con timeout personalizado

### 2. Detección de Servicios y Versiones

El módulo puede detectar servicios y versiones de software en los hosts escaneados.

- **Detalles obtenidos**:
  - Versiones de servicios
  - Información del sistema operativo
  - Tipos de servicios (HTTP, SSH, FTP, etc.)

### 3. Escaneo de Vulnerabilidades Básicas

El módulo incluye detección básica de vulnerabilidades conocidas.

- **Tipos de vulnerabilidades detectadas**:
  - Servicios con versiones conocidas vulnerables
  - Configuraciones inseguras comunes
  - Puertos abiertos no necesarios

### 4. Generación de Reportes

El módulo genera reportes detallados en diferentes formatos.

- **Formatos de salida**:
  - Texto plano
  - JSON
  - XML
  - HTML (para visualización en las apps móviles)

## 🛠 Configuración

### 1. Configuración en el Agente de Termux

El módulo Nmap Avanzado se configura en el archivo `ame_config_template.json` del agente de Termux:

```json
{
  "nmap": {
    "enabled": true,
    "timeout": 30,
    "max_hosts": 256,
    "scan_types": ["syn", "service", "osdetect"],
    "output_format": "json",
    "verbose": true
  }
}
```

### 2. Configuración en las Apps Móviles

Las aplicaciones móviles pueden configurar los parámetros de escaneo mediante la interfaz de usuario o archivos de configuración.

#### Ejemplo de configuración en APK AME:

```json
{
  "nmap": {
    "default_scan": {
      "target": "192.168.1.0/24",
      "ports": "1-1000,8080,8443",
      "scan_type": "syn",
      "output": "json"
    },
    "advanced_options": {
      "aggressive": true,
      "version_intensity": 9,
      "os_detection": true
    }
  }
}
```

## 🔄 Ejecución de Escaneos

### 1. Desde el Agente de Termux

El agente de Termux puede ejecutar escaneos programados o manuales:

```bash
python modules/osint_username.py --target 192.168.1.1 --scan-type syn --ports 1-1000
```

### 2. Desde las Apps Móviles

Las aplicaciones móviles proporcionan una interfaz gráfica para ejecutar escaneos:

1. Abre la aplicación APK AME o App Maid.
2. Ve a la sección de "Módulos Tácticos".
3. Selecciona "Nmap Avanzado".
4. Configura los parámetros del escaneo.
5. Ejecuta el escaneo.

## 📌 Ejemplos de Comandos

### 1. Escaneo Básico de Puertos

```bash
python modules/osint_username.py --target 192.168.1.1 --ports 1-1000
```

### 2. Escaneo Avanzado con Detección de OS

```bash
python modules/osint_username.py --target 192.168.1.1 --scan-type syn --ports 1-1000 --os-detect
```

### 3. Escaneo de Red Local Completo

```bash
python modules/osint_username.py --target 192.168.1.0/24 --scan-type syn --ports 1-65535 --max-hosts 256
```

### 4. Escaneo con Salida en Formato HTML

```bash
python modules/osint_username.py --target 192.168.1.1 --output-format html > scan_report.html
```

## 📊 Visualización de Resultados

Los resultados de los escaneos pueden visualizarse en:

1. **Consola de Termux**: Los resultados se muestran directamente en la terminal.
2. **Apps Móviles**: Los resultados se muestran en formato HTML en la interfaz de las aplicaciones.
3. **Servidor Central**: Los resultados se almacenan en el buffer del servidor central y pueden consultarse mediante la API.

## 🔗 Enlaces Relacionados

- [[01_Arquitectura/03_Nodo_Termux]]
- [[03_Módulos_Tácticos/02_OSINT_Sherlock]]
- [[03_Módulos_Tácticos/03_Keylogger_Táctico]]

## 📌 Notas Importantes

- **Uso legítimo**: Este módulo está diseñado para auditoría de infraestructura propia y debe usarse de manera ética y legal.
- **Seguridad**: Los escaneos pueden detectar información sensible. Asegúrate de tener autorización para escanear redes que no son de tu propiedad.
- **Enlaces internos**: Utiliza el formato `[[Archivo]]` para mantener la integridad del grafo de Obsidian.
- **Rendimiento**: Escaneos extensos pueden consumir muchos recursos. Configura adecuadamente los parámetros para evitar sobrecargar la red.

## 📝 Ejemplo de Uso Completo

1. **Configuración**:
   - Configura el módulo en `ame_config_template.json` del agente de Termux.
   - Configura los parámetros en la aplicación móvil si es necesario.

2. **Ejecución**:
   - Ejecuta un escaneo básico desde Termux:
     ```bash
     python modules/osint_username.py --target 192.168.1.1 --ports 1-1000
     ```
   - Ejecuta un escaneo avanzado desde la aplicación móvil:
     - Selecciona el módulo Nmap Avanzado.
     - Configura el rango de direcciones IP y los puertos a escanear.
     - Ejecuta el escaneo y visualiza los resultados en la interfaz.

3. **Análisis**:
   - Revisa los resultados en la consola o en la interfaz de la aplicación.
   - Exporta los resultados a un archivo para análisis posterior.

## 📌 Solución de Problemas

### 1. Errores de Conexión

- Verifica que la IP de destino sea correcta.
- Asegúrate de que el host de destino esté en línea.
- Verifica que no haya firewalls bloqueando el escaneo.

### 2. Escaneos Lentos

- Reduce el número de hosts a escanear.
- Limita los puertos a escanear.
- Aumenta el timeout si es necesario.

### 3. Resultados Incompletos

- Verifica que los puertos estén abiertos y accesibles.
- Asegúrate de que el host de destino responda a las solicitudes.
- Prueba con diferentes tipos de escaneo (SYN, TCP Connect, etc.).

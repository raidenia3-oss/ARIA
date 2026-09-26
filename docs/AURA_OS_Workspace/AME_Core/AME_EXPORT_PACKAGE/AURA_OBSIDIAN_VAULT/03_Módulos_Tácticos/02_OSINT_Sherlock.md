# Módulo OSINT/Sherlock

Este documento describe el módulo **OSINT/Sherlock** integrado en el ecosistema AURA/AME, que permite realizar búsquedas de inteligencia de fuentes abiertas (OSINT) para encontrar información sobre usuarios, dominios y organizaciones.

## 🔧 Funcionalidades Principales

### 1. Búsqueda de Usuarios en Redes Sociales

El módulo puede buscar información de usuarios en múltiples plataformas de redes sociales.

- **Plataformas soportadas**:
  - Twitter/X
  - LinkedIn
  - Facebook
  - GitHub
  - Instagram
  - Reddit
  - YouTube
  - TikTok
  - Discord

- **Información obtenida**:
  - Perfiles públicos
  - Historial de actividad
  - Conexiones y relaciones
  - Información de contacto

### 2. Búsqueda de Dominios

El módulo puede realizar búsquedas de información sobre dominios y subdominios.

- **Tipos de información**:
  - Registros WHOIS
  - Subdominios
  - Información de servidores DNS
  - Historial de cambios en el dominio
  - Información de certificados SSL/TLS

### 3. Búsqueda de Reputación en Línea

El módulo evalúa la reputación en línea de usuarios, dominios y organizaciones.

- **Métricas de reputación**:
  - Actividad en redes sociales
  - Menciones en medios
  - Relaciones con otras entidades
  - Historial de seguridad (si está disponible)

### 4. Integración con Sherlock

El módulo incluye una integración con [Sherlock](https://github.com/sherlock-project/sherlock), una herramienta popular para encontrar perfiles de usuarios en redes sociales.

- **Funcionalidades de Sherlock**:
  - Búsqueda de perfiles por nombre de usuario
  - Soporte para múltiples plataformas
  - Actualizaciones periódicas de la base de datos

## 🛠 Configuración

### 1. Configuración en el Agente de Termux

El módulo OSINT/Sherlock se configura en el archivo `ame_config_template.json` del agente de Termux:

```json
{
  "osint": {
    "enabled": true,
    "sherlock": {
      "enabled": true,
      "update_db": true,
      "timeout": 60,
      "max_results": 50
    },
    "social_media": {
      "platforms": ["twitter", "linkedin", "github", "instagram"],
      "api_keys": {
        "twitter": "tu_api_key_twitter",
        "linkedin": "tu_api_key_linkedin"
      }
    }
  }
}
```

### 2. Configuración en las Apps Móviles

Las aplicaciones móviles pueden configurar los parámetros de OSINT mediante la interfaz de usuario o archivos de configuración.

#### Ejemplo de configuración en APK AME:

```json
{
  "osint": {
    "default_search": {
      "target": "username",
      "platforms": ["twitter", "github", "linkedin"],
      "depth": "medium"
    },
    "reputation": {
      "enabled": true,
      "threshold": 70
    }
  }
}
```

## 🔄 Ejecución de Búsquedas

### 1. Desde el Agente de Termux

El agente de Termux puede ejecutar búsquedas OSINT programadas o manuales:

```bash
python modules/osint_username.py --target username --platforms twitter,github,linkedin
```

Para usar Sherlock específicamente:

```bash
python modules/osint_reputation.py --target username --update-db
```

### 2. Desde las Apps Móviles

Las aplicaciones móviles proporcionan una interfaz gráfica para ejecutar búsquedas OSINT:

1. Abre la aplicación APK AME o App Maid.
2. Ve a la sección de "Módulos Tácticos".
3. Selecciona "OSINT/Sherlock".
4. Configura los parámetros de la búsqueda (nombre de usuario, plataformas, profundidad).
5. Ejecuta la búsqueda.

## 📌 Ejemplos de Comandos

### 1. Búsqueda Básica de Usuario

```bash
python modules/osint_username.py --target john_doe --platforms twitter,github
```

### 2. Búsqueda Avanzada con Sherlock

```bash
python modules/osint_reputation.py --target john_doe --update-db --platforms all
```

### 3. Búsqueda de Dominio

```bash
python modules/osint_reputation.py --target example.com --type domain
```

### 4. Búsqueda de Reputación en Línea

```bash
python modules/osint_reputation.py --target john_doe --reputation-only
```

## 📊 Visualización de Resultados

Los resultados de las búsquedas OSINT pueden visualizarse en:

1. **Consola de Termux**: Los resultados se muestran directamente en la terminal.
2. **Apps Móviles**: Los resultados se muestran en formato estructurado en la interfaz de las aplicaciones.
3. **Servidor Central**: Los resultados se almacenan en el buffer del servidor central y pueden consultarse mediante la API.

## 🔗 Enlaces Relacionados

- [[01_Arquitectura/03_Nodo_Termux]]
- [[03_Módulos_Tácticos/01_Nmap_Advanced]]
- [[03_Módulos_Tácticos/03_Keylogger_Táctico]]

## 📌 Notas Importantes

- **Uso legítimo**: Este módulo está diseñado para investigación legítima y auditoría de infraestructura propia. Asegúrate de cumplir con las leyes y políticas de privacidad al usar este módulo.
- **Limitaciones**: Algunas plataformas pueden tener limitaciones en la cantidad de búsquedas que puedes realizar.
- **API Keys**: Algunas plataformas requieren API keys para acceder a información adicional. Configúralas en el archivo de configuración.
- **Enlaces internos**: Utiliza el formato `[[Archivo]]` para mantener la integridad del grafo de Obsidian.
- **Rendimiento**: Búsquedas extensas pueden consumir muchos recursos y tiempo. Configura adecuadamente los parámetros para evitar sobrecargar los servicios.

## 📝 Ejemplo de Uso Completo

1. **Configuración**:
   - Configura el módulo en `ame_config_template.json` del agente de Termux.
   - Configura las API keys necesarias si es requerido.
   - Configura los parámetros en la aplicación móvil si es necesario.

2. **Ejecución**:
   - Ejecuta una búsqueda básica desde Termux:
     ```bash
     python modules/osint_username.py --target john_doe --platforms twitter,github
     ```
   - Ejecuta una búsqueda avanzada desde la aplicación móvil:
     - Selecciona el módulo OSINT/Sherlock.
     - Configura el nombre de usuario o dominio a buscar.
     - Selecciona las plataformas a buscar.
     - Ejecuta la búsqueda y visualiza los resultados en la interfaz.

3. **Análisis**:
   - Revisa los resultados en la consola o en la interfaz de la aplicación.
   - Exporta los resultados a un archivo para análisis posterior.
   - Utiliza la información para evaluar la reputación en línea o realizar auditorías de seguridad.

## 📌 Solución de Problemas

### 1. Errores de Conexión a Plataformas

- Verifica que las API keys sean correctas y estén configuradas.
- Asegúrate de que las plataformas estén disponibles y no bloqueen el acceso.
- Verifica que no haya restricciones geográficas o de IP que impidan el acceso.

### 2. Resultados Limitados

- Algunas plataformas pueden limitar los resultados para cuentas no autenticadas.
- Prueba con diferentes plataformas para obtener más información.
- Considera usar cuentas premium si es necesario para acceder a más datos.

### 3. Búsquedas Lentas

- Reduce el número de plataformas a buscar.
- Limita la profundidad de la búsqueda.
- Aumenta el timeout si es necesario.

### 4. Actualización de Base de Datos de Sherlock

- Ejecuta manualmente la actualización de la base de datos con:
  ```bash
  python modules/osint_reputation.py --update-db
  ```
- Asegúrate de tener suficiente espacio en disco para la base de datos.

## 🔒 Consideraciones de Privacidad y Legalidad

- **Consentimiento**: Solo busca información de personas o entidades que hayan hecho pública su información.
- **Leyes de Privacidad**: Cumple con las leyes de privacidad como GDPR, CCPA, etc.
- **Términos de Servicio**: Respeta los términos de servicio de cada plataforma.
- **Uso Ético**: Usa este módulo solo para fines legítimos y éticos.

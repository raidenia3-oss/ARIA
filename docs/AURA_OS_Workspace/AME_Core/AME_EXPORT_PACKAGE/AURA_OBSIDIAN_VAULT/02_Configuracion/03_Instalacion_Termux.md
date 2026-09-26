# Instalación del Agente AME en Termux

Este documento describe los pasos para instalar y configurar el agente AME en un dispositivo con Termux.

## 📱 Requisitos Previos

1. **Termux instalado**: Debes tener Termux instalado en tu dispositivo Android.
   - Descarga desde [F-Droid](https://f-droid.org/es/packages/com.termux/).
   - Instala la versión de Termux sin root si es posible.

2. **Permisos necesarios**:
   - Permisos de almacenamiento para acceder a archivos.
   - Permisos de red para conectarse al servidor central.

3. **Dependencias**:
   - Python 3.8 o superior.
   - pip (gestor de paquetes de Python).

## 🛠 Instalación del Agente AME

### 1. Actualizar Termux

Primero, actualiza Termux y sus paquetes:

```bash
pkg update && pkg upgrade -y
```

### 2. Instalar Dependencias

Instala las dependencias necesarias para el agente AME:

```bash
pkg install python -y
pip install --upgrade pip
pip install requests ollama python-dotenv
```

### 3. Configurar el Entorno

Crea un archivo `.env` en el directorio del agente con las siguientes variables:

```bash
echo "SERVER_URL=http://192.168.1.100:8000" > .env
echo "AGENT_ID=termux-node-$(date +%s)" >> .env
```

### 4. Descargar el Agente AME

Descarga el paquete de exportación AME a tu dispositivo:

1. Transfiere el archivo ZIP `AME_EXPORT_PACKAGE.zip` a tu dispositivo móvil.
2. Extrae el contenido en un directorio de Termux:

```bash
unzip AME_EXPORT_PACKAGE.zip -d ~/ame_agent
cd ~/ame_agent/TERMUX_AGENT
```

### 5. Configurar el Archivo de Configuración

Edita el archivo `ame_config_template.json` para configurar parámetros específicos:

```bash
nano ame_config_template.json
```

Ejemplo de configuración:

```json
{
  "sync_interval": 30,
  "max_retries": 3,
  "timeout": 10,
  "hooks": {
    "on_start": ["echo 'Agente AME iniciado en Termux'"],
    "on_sync": ["date >> /sdcard/ame_sync.log"]
  }
}
```

### 6. Instalar el Script de Inicio

Crea un script de inicio para el agente AME:

```bash
echo '#!/data/data/com.termux/bin/bash' > ~/ame_start.sh
echo 'cd ~/ame_agent/TERMUX_AGENT' >> ~/ame_start.sh
echo 'python ame_termux_node.py' >> ~/ame_start.sh
chmod +x ~/ame_start.sh
```

### 7. Configurar Termux para Iniciar el Agente

Agrega el script al archivo de inicio de Termux:

```bash
echo '~/ame_start.sh &' >> ~/.bashrc
```

### 8. Iniciar el Agente

Inicia el agente AME:

```bash
~/ame_start.sh
```

## 🔄 Configuración Adicional

### 1. Configuración de Ganchos (Hooks)

Puedes configurar ganchos para ejecutar comandos antes y después de la sincronización:

```json
"hooks": {
  "on_start": ["echo 'Iniciando agente AME'"],
  "on_sync": ["date >> /sdcard/ame_sync.log"],
  "on_error": ["echo 'Error en la sincronización' >> /sdcard/ame_errors.log"]
}
```

### 2. Configuración de Sincronización

Configura el intervalo de sincronización en el archivo `ame_config_template.json`:

```json
{
  "sync_interval": 60, // Sincronización cada 60 segundos
  "max_retries": 5, // Máximo de reintentos en caso de error
  "timeout": 15 // Tiempo de espera en segundos
}
```

## 📌 Solución de Problemas

### 1. Error de Conexión al Servidor

- Verifica que la IP del servidor central sea correcta en el archivo `.env`.
- Asegúrate de que el servidor central esté en ejecución.
- Verifica que ambos dispositivos estén en la misma red.

### 2. Permisos Insuficientes

- Asegúrate de que Termux tenga los permisos necesarios.
- Ejecuta `termux-setup-storage` para configurar el acceso a almacenamiento.

### 3. Dependencias Faltantes

- Ejecuta `pip install -r requirements.txt` si hay un archivo de requisitos disponible.

## 🔗 Enlaces Relacionados

- [[01_Arquitectura/03_Nodo_Termux]]
- [[02_Configuracion/01_API_Keys_OpenRouter]]
- [[02_Configuracion/02_IP_Local_Celular]]

## 📌 Notas Importantes

- **Seguridad**: Nunca compartas tus credenciales o configuraciones sensibles.
- **Uso legítimo**: Este agente está diseñado para auditoría y gestión de infraestructura propia.
- **Enlaces internos**: Utiliza el formato `[[Archivo]]` para mantener la integridad del grafo de Obsidian.
- **Actualizaciones**: Para actualizar el agente, descarga la última versión del paquete y reemplaza los archivos en el directorio `~/ame_agent/TERMUX_AGENT`.

## 📝 Ejemplo de Uso

1. **Iniciar el agente**:

   ```bash
   ~/ame_start.sh
   ```

2. **Verificar el estado**:

   ```bash
   ps aux | grep ame_termux_node.py
   ```

3. **Reiniciar el agente**:

   ```bash
   pkill -f ame_termux_node.py
   ~/ame_start.sh
   ```

4. **Verificar logs**:
   ```bash
   cat /sdcard/ame_sync.log
   ```

## 📌 Configuración Avanzada

### 1. Configuración de Proxies

Si necesitas usar un proxy para conectarte al servidor central, configúralo en el archivo `.env`:

```bash
echo "HTTP_PROXY=http://proxy-ip:proxy-port" >> .env
echo "HTTPS_PROXY=http://proxy-ip:proxy-port" >> .env
```

### 2. Configuración de SSL/TLS

Si el servidor central usa HTTPS, asegúrate de que el certificado sea válido o configura la verificación de certificados en el código del agente.

### 3. Configuración de Autenticación

Si el servidor central requiere autenticación, configura las credenciales en el archivo `.env`:

```bash
echo "API_KEY=tu_api_key_aqui" >> .env
```

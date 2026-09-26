# 🚀 Instrucciones para Reiniciar el Servidor Estático de AURA

## 📋 Problema Resuelto
Se ha corregido el problema de acceso desde la red local al servidor estático. Ahora el servidor escucha en **0.0.0.0** en lugar de solo en **localhost**, permitiendo que cualquier dispositivo en la misma red WiFi pueda acceder a los archivos, incluyendo el APK para actualizaciones OTA.

## 🔧 Acciones Realizadas
1. **Modificación del servidor estático**: El archivo `Shadow-Core/static_server.py` ahora escucha en todas las interfaces de red (`0.0.0.0`).
2. **Verificación de archivos**: El servidor verifica que el directorio `dist/` y el archivo `AME_Client_v1.apk` existan antes de iniciar.
3. **Mensajes claros**: El servidor muestra mensajes informativos sobre cómo acceder desde la red local.

## 🔄 Cómo Reiniciar el Servidor

Para aplicar los cambios, sigue estos pasos:

### 1️⃣ **Compilar el APK (si es necesario)**
Si has realizado cambios en el código de AME, primero compila el APK actualizado:
```bash
COMPILAR_AME.bat
```

### 2️⃣ **Ejecutar el Script de Inicio**
Ejecuta el script que inicia todos los servicios de AURA, incluyendo el servidor estático:
```bash
cd Setup
start_aura_with_tunnel_and_ota.bat
```

### 3️⃣ **Verificar que el Servidor Esté Funcionando**
Abre una terminal y verifica que el servidor esté escuchando en el puerto 8000:
```bash
netstat -ano | findstr 8000
```
Deberías ver una línea similar a:
```
TCP    0.0.0.0:8000           0.0.0.0:0              LISTENING
```

### 4️⃣ **Probar el Acceso desde el Celular**
Desde el dispositivo móvil (AME), verifica que puedas acceder a:
```
http://192.168.3.10:8000/descargar-ame
```
(Reemplaza `192.168.3.10` con la IP real de tu PC en la red local)

## 📌 Notas Importantes

1. **IP de la PC**: Asegúrate de que la IP de tu PC no haya cambiado. Si lo ha hecho, actualiza la configuración en AME para usar la nueva IP.

2. **Firewall**: Verifica que el firewall de tu sistema permita conexiones entrantes en el puerto 8000:
   ```bash
   netsh advfirewall firewall add rule name="AURA Static Server" dir=in action=allow protocol=TCP localport=8000
   ```

3. **Router**: Asegúrate de que no haya configuraciones en tu router que bloqueen el puerto 8000.

4. **Pruebas**: Después de reiniciar, prueba el sistema OTA desde AME para verificar que las actualizaciones funcionen correctamente.

## 🔒 Seguridad
El servidor estático solo sirve archivos desde el directorio `dist/` y no ejecuta código, por lo que el riesgo de seguridad es mínimo. Sin embargo, se recomienda:
- Usar una red local segura y confiable
- No exponer el servidor a internet
- Verificar siempre la integridad de los archivos descargados

## 🎉 ¡Listo!
Una vez que hayas ejecutado el script `start_aura_with_tunnel_and_ota.bat`, el sistema estará listo para:
- Actualizaciones OTA automáticas desde cualquier dispositivo en la red local
- Acceso a todos los archivos estáticos de AURA
- Funcionamiento completo del Radar de Reconocimiento Pasivo Unificado

Si encuentras algún problema, revisa los logs del servidor o contacta al equipo de soporte técnico.
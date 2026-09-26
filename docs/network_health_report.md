# Network Health Report
**Fecha:** 2026-06-23 21:03:57
**Estado:** 1/4 endpoints operativos
**Resultado:** ALERTA: 3 fallos

## Endpoints Verificados

### OK HF Space
- **URL:** `https://raiden456-slut.hf.space`
- **HTTP:** {'status': 200, 'body': '{"status":"ok"}'}
- **DNS:** Resolucion DNS OK
- **Estado:** OPERATIVO

### FAIL Railway API
- **URL:** `http://localhost:8000`
- **HTTP:** Error de red: [WinError 10061] No se puede establecer una conexión ya que el equipo de destino denegó expresamente dicha conexión
- **DNS:** Resolucion DNS OK
- **Estado:** FALLO

### FAIL Vercel Frontend
- **URL:** `http://localhost:3000`
- **HTTP:** Error de red: [WinError 10061] No se puede establecer una conexión ya que el equipo de destino denegó expresamente dicha conexión
- **DNS:** Resolucion DNS OK
- **Estado:** FALLO

### FAIL n8n Render
- **URL:** `https://aura-n8n.onrender.com`
- **HTTP:** Error de red: Not Found
- **DNS:** Resolucion DNS OK
- **Estado:** FALLO


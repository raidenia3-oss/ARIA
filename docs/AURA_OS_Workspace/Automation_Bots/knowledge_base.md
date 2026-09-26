# Base de Conocimiento - RollerCoin Bot

## Configuración Actual
- `check_interval`: 60 segundos
- `max_retries`: 3
- `wait_times`: {
  "login": 10,
  "game_load": 15,
  "action": 5,
  "captcha": 30
}

## Errores Conocidos y Soluciones

### Errores de Red
- **Solución:** Verificar conexión a internet, reiniciar router, probar con VPN
- **Ajuste:** Aumentar `max_retries` a 5 cuando hay inestabilidad
- **Ocurrencias:** 0

### Errores de UI
- **Solución:** Aumentar tiempos de espera, verificar selectores, actualizar bot
- **Ajuste:** Multiplicar `wait_times` por 1.5 después de 3 fallos consecutivos
- **Ocurrencias:** 0

### Errores de CAPTCHA
- **Solución:** Reducir velocidad de acciones, usar proxies, implementar solución manual
- **Ajuste:** Aumentar `wait_times[captcha]` a 60 segundos
- **Ocurrencias:** 0

### Errores de Login
- **Solución:** Verificar credenciales, renovar sesión, limpiar cookies
- **Ajuste:** Reiniciar sesión y limpiar caché
- **Ocurrencias:** 0

### Errores de Rate Limit
- **Solución:** Aumentar delays entre acciones, implementar backoff exponencial
- **Ajuste:** Implementar backoff exponencial (2^retry)
- **Ocurrencias:** 0

### Errores de Juego
- **Solución:** Reiniciar juego, verificar mantenimiento, cambiar de juego
- **Ajuste:** Aumentar `check_interval` a 120 segundos
- **Ocurrencias:** 0

### Errores de Verificación
- **Solución:** Obtener nuevo código de verificación, verificar integración con Gmail
- **Ajuste:** Aumentar intervalo de verificación a 90 segundos
- **Ocurrencias:** 0

## Historial de Errores

## Estadísticas
- `total_errors`: 0
- `errors_by_type`: {}
# **Propuesta: Integración de LM Studio (Gemma 4) como Capa de Inferencia Local**

**Autor:** Cline
**Fecha:** 05/06/2026

---

## **Contexto**

El sistema AURA requiere procesamiento de datos complejos como:

- **Parseo de logs crudos de Termux** (formato no estructurado).
- **Limpieza de JSONs sucios** devueltos por Shodan/OSINT.
- **Análisis estructural de paquetes CSI** de RuView.

Actualmente, estas tareas dependen de APIs de la nube, lo que genera costos elevados en tokens y latencia. **LM Studio con Gemma 4** permite procesar estas tareas de manera local, reduciendo costos y mejorando la privacidad.

---

## **Objetivos**

1. **Reducir costos de tokens** al procesar tareas localmente.
2. **Mejorar la privacidad** al evitar enviar datos sensibles a la nube.
3. **Aumentar la resiliencia** con un mecanismo de fallback automático a la nube.
4. **Optimizar el rendimiento** al procesar datos en tiempo real sin depender de latencia externa.

---

## **Alternativas Consideradas**

| Alternativa                   | Pros                                                                     | Contras                                                               |
| ----------------------------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------- |
| **LM Studio (Gemma 4) Local** | - Bajo costo (sin tokens).<br>- Alto rendimiento.<br>- Privacidad local. | - Requiere configuración inicial.<br>- Dependencia de hardware local. |
| **APIs de la Nube (OpenAI)**  | - Sin configuración.<br>- Soporte garantizado.                           | - Costos altos en tokens.<br>- Latencia.<br>- Riesgo de privacidad.   |
| **Ollama Local**              | - Alternativa open-source.<br>- Bajo costo.                              | - Menor optimización para Gemma 4.<br>- Menos soporte para APIs.      |

---

## **Tareas**

### **1. Implementación del Router de Inferencia Local**

- [x] Crear `AURA_Core/local_llm_router.py` (completado).
- [ ] Integrar el router en los módulos de procesamiento de datos (OSINT, RuView, logs de Termux).

### **2. Configuración de LM Studio**

- [ ] Configurar LM Studio con Gemma 4 en la PC.
- [ ] Exponer el endpoint en `http://localhost:1234/v1` (formato OpenAI API).

### **3. Integración en Módulos Existentes**

- [ ] Modificar `osint_scraper.py` para usar el router local en tareas de limpieza de JSON.
- [ ] Modificar `osint_radar.py` para procesar datos CSI con el modelo local.
- [ ] Modificar `venice_shodan_scanner.py` para limpiar respuestas de Shodan localmente.

### **4. Mecanismo de Fallback**

- [ ] Implementar lógica de fallback automático si LM Studio no responde.
- [ ] Configurar tiempo de espera y retries para evitar bloqueos.

### **5. Pruebas y Validación**

- [ ] Probar el router con datos de ejemplo (logs, JSONs sucios, paquetes CSI).
- [ ] Validar que el fallback a la nube funcione correctamente.

---

## **Impacto Esperado**

### **Beneficios**

✅ **Reducción de costos:** Procesamiento local evita consumo de tokens en la nube.
✅ **Mejor privacidad:** Datos sensibles no salen del entorno local.
✅ **Mayor resiliencia:** Fallback automático a la nube si el local falla.
✅ **Rendimiento mejorado:** Procesamiento en tiempo real sin latencia externa.

### **Riesgos**

⚠ **Dependencia de hardware local:** Si LM Studio no está disponible, se usa el fallback.
⚠ **Configuración inicial:** Requiere instalar y configurar LM Studio en la PC.

---

## **Detalles Técnicos**

### **1. Arquitectura del Router**

El script `local_llm_router.py` implementa:

- **Conexión a LM Studio** en `http://localhost:1234/v1` (formato OpenAI API).
- **Fallback automático** a APIs de la nube si el local no responde.
- **Métodos principales:**
  - `chat_completion()`: Para procesamiento de texto (logs, JSONs).
  - `embeddings()`: Para análisis estructural (CSI, datos OSINT).
  - `check_availability()`: Verifica si LM Studio está disponible.

### **2. Ejemplo de Uso**

```python
router = LocalLLMRouter()

# Procesar un JSON sucio de Shodan
response = router.chat_completion(
    model="gemma-4",
    messages=[
        {"role": "system", "content": "Eres un experto en limpieza de datos OSINT."},
        {"role": "user", "content": "Limpia este JSON de Shodan: {\"data\": [\"raw\", \"json\", \"sin\", \"formato\"]}"}
    ],
    max_tokens=200
)
```

### **3. Integración con Módulos Existentes**

- **OSINT:** Usar `chat_completion` para limpiar respuestas de Shodan.
- **RuView:** Usar `embeddings` para analizar paquetes CSI.
- **Logs de Termux:** Usar `chat_completion` para parsear logs crudos.

---

## **Próximos Pasos**

1. **Aprobación de la propuesta** (esperando comando `opsx apply`).
2. **Configuración de LM Studio** en la PC.
3. **Integración en módulos clave** (OSINT, RuView, logs de Termux).
4. **Pruebas de rendimiento y fallback**.

---

**Nota:** Este cambio sigue el protocolo OPSX y requiere aprobación explícita antes de aplicar modificaciones al código base.

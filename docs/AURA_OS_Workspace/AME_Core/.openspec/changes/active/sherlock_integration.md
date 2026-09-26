# **Propuesta: Integración de Sherlock en Venice Modules**

**Autor:** Cline
**Fecha:** 06/06/2026

---

## **Contexto**

El sistema AURA requiere potenciar su capacidad de reconocimiento digital mediante la integración de **Sherlock**, una herramienta especializada en la búsqueda de perfiles en redes sociales. Actualmente, los módulos OSINT de AURA no están optimizados para este tipo de búsquedas, lo que limita la precisión y cobertura en la identificación de cuentas.

Sherlock es una herramienta de código abierto que escanea múltiples plataformas para verificar la existencia de un perfil asociado a un alias. **No modificaremos el código base de Sherlock**, sino que lo envolveremos en un script que ejecute Sherlock como un subproceso y procese su salida para integrarla en el ecosistema AURA.

---

## **Objetivos**

1. **Integración no invasiva:** Usar Sherlock como un subproceso sin modificar su código base.
2. **Procesamiento con Gemma 4:** Capturar la salida en bruto de Sherlock y enviarla a `local_llm_router.py` para limpiarla y estructurarla.
3. **Resultado estructurado:** Devolver un JSON con solo las redes sociales donde el perfil **EXISTE realmente**.
4. **Integración con Discord:** Añadir un comando `/hunt [alias]` que dispare este flujo.

---

## **Alternativas Consideradas**

| Alternativa                         | Pros                                                                   | Contras                                                                |
| ----------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| **Sherlock (wrapper)**              | - Precisión en detección de perfiles.<br>- Código abierto y mantenido. | - Requiere procesamiento de salida en bruto.<br>- Dependencia externa. |
| **APIs de OSINT personalizadas**    | - Control total sobre el flujo.<br>- Sin dependencias externas.        | - Menor precisión.<br>- Más desarrollo requerido.                      |
| **Ollama + Prompts personalizados** | - Sin dependencias externas.<br>- Flexibilidad.                        | - Menor precisión en detección de perfiles.<br>- Más lento.            |

---

## **Tareas**

### **1. Creación del Wrapper para Sherlock**

- [ ] Crear `venice_modules/osint_sherlock_wrapper.py`:
  - Ejecutar Sherlock como un subproceso con `subprocess.run()`.
  - Capturar la salida en bruto.
  - Enviar la salida a `local_llm_router.py` para limpieza y estructuración.
  - Devolver un JSON con solo las redes sociales donde el perfil existe.

### **2. Integración con el Router de Gemma 4**

- [ ] Modificar `local_llm_router.py` para manejar la salida de Sherlock.
- [ ] Configurar un prompt específico para limpiar y estructurar la salida de Sherlock.

### **3. Integración con Discord**

- [ ] Modificar `discord_bot.py` para añadir el comando `/hunt [alias]`.
- [ ] Validar que el comando dispare el flujo completo (Sherlock → Gemma 4 → JSON estructurado).

### **4. Pruebas y Validación**

- [ ] Probar el wrapper con alias de ejemplo.
- [ ] Validar que el JSON devuelto contenga solo redes sociales donde el perfil existe.
- [ ] Probar el comando `/hunt` en Discord.

---

## **Detalles Técnicos**

### **1. Arquitectura del Wrapper**

El script `osint_sherlock_wrapper.py` implementará:

- **Ejecución de Sherlock:** Usar `subprocess.run()` para ejecutar Sherlock con un alias específico.
- **Captura de salida:** Capturar la salida en bruto de Sherlock.
- **Procesamiento con Gemma 4:** Enviar la salida a `local_llm_router.py` para limpieza y estructuración.
- **Resultado estructurado:** Devolver un JSON con solo las redes sociales donde el perfil existe.

**Ejemplo de salida esperada:**

```json
{
  "alias": "ejemplo_alias",
  "platforms_found": [
    {
      "platform": "github",
      "url": "https://github.com/ejemplo_alias",
      "status": "found"
    },
    {
      "platform": "twitter",
      "url": "https://twitter.com/ejemplo_alias",
      "status": "found"
    }
  ],
  "platforms_not_found": [
    {
      "platform": "reddit",
      "status": "not_found"
    }
  ]
}
```

### **2. Integración con Discord**

El comando `/hunt [alias]` en Discord:

1. Recibirá un alias como argumento.
2. Ejecutará el wrapper de Sherlock.
3. Devolverá un embed con los resultados estructurados.

**Ejemplo de uso:**

```bash
/hunt ejemplo_alias
```

**Resultado en Discord:**

```
🔍 Resultado de Sherlock para 'ejemplo_alias':
- GitHub: ✅ https://github.com/ejemplo_alias
- Twitter: ✅ https://twitter.com/ejemplo_alias
- Reddit: ❌ No encontrado
```

---

## **Impacto Esperado**

### **Beneficios**

✅ **Precisión mejorada:** Sherlock es especializado en la detección de perfiles en redes sociales.
✅ **Integración no invasiva:** No se modifica el código base de Sherlock.
✅ **Procesamiento local:** Uso de Gemma 4 para limpiar y estructurar la salida.
✅ **Flujo automatizado:** Integración completa con Discord mediante el comando `/hunt`.

### **Riesgos**

⚠ **Dependencia externa:** Sherlock es una herramienta externa que podría cambiar en el futuro.
⚠ **Procesamiento de salida:** Requiere limpieza y estructuración con Gemma 4.
⚠ **Tiempo de ejecución:** Sherlock puede ser lento en algunas plataformas.

---

## **Próximos Pasos**

1. **Aprobación de la propuesta** (esperando comando `opsx apply`).
2. **Implementación del wrapper** (`osint_sherlock_wrapper.py`).
3. **Integración con Gemma 4** y Discord.
4. **Pruebas y validación** del flujo completo.

---

**Nota:** Este cambio sigue el protocolo OPSX y requiere aprobación explícita antes de aplicar modificaciones al código base.

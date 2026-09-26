# **Propuesta: Integración de ODiscord (Forensics de Discord) en Venice Modules**

**Autor:** Cline
**Fecha:** 06/06/2026

---

## **Contexto**

El sistema AURA requiere potenciar sus capacidades de **OSINT forense en Discord**, permitiendo extraer metadatos profundos de usuarios y servidores sin violar los términos de servicio de Discord. Actualmente, no existe un módulo especializado en la extracción de información forense de Discord, como fechas de creación de banners, avatares históricos, flags de usuario, o información pública de servidores.

La integración de **ODiscord** (inspirado en el repositorio I2rys/ODiscord) permitirá extraer información pública de manera pasiva, respetando los límites de la API de Discord y protegiendo nuestro token principal.

---

## **Objetivos**

1. **Extracción de metadatos forenses:** Crear un módulo que extraiga información pública de usuarios y servidores en Discord.
2. **Uso de la API oficial:** Utilizar `discord.py` para interactuar con la API de Discord de manera segura.
3. **Recolección pasiva:** Asegurar que el módulo solo realice OSINT sin violar los rate limits.
4. **Integración con Discord:** Añadir un comando `/audit_discord [User_ID o Invite_Link]` para disparar el flujo de extracción.

---

## **Alternativas Consideradas**

| Alternativa             | Pros                                                            | Contras                                                                  |
| ----------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------ |
| **ODiscord (wrapper)**  | - Extracción de metadatos forenses.<br>- Uso de la API oficial. | - Requiere manejo cuidadoso de rate limits.<br>- Dependencia de Discord. |
| **APIs personalizadas** | - Control total sobre el flujo.<br>- Sin dependencias externas. | - Menor precisión en metadatos.<br>- Más desarrollo requerido.           |
| **Scraping no oficial** | - Sin dependencia de API.<br>- Flexibilidad.                    | - Riesgo de violar TOS de Discord.<br>- Menor precisión.                 |

---

## **Tareas**

### **1. Creación del Módulo ODiscord**

- [ ] Crear `venice_modules/osint_discord_forensics.py`:
  - Utilizar `discord.py` para extraer metadatos públicos.
  - Implementar funciones para extraer:
    - Información de usuarios (ID, nombre, avatares históricos, flags).
    - Información de servidores (fecha de creación del banner, miembros públicos, roles).
    - Metadatos de invitaciones (fecha de creación, creador, permisos).
  - Asegurar que el módulo respete los rate limits de la API.

### **2. Integración con el Bot de Discord**

- [ ] Modificar `discord_bot.py` para añadir el comando `/audit_discord [User_ID o Invite_Link]`.
- [ ] Validar que el comando dispare el flujo de extracción de manera segura.

### **3. Pruebas y Validación**

- [ ] Probar el módulo con IDs de usuario y enlaces de invitación de ejemplo.
- [ ] Validar que la extracción no viole los rate limits de la API.
- [ ] Probar el comando `/audit_discord` en Discord.

---

## **Detalles Técnicos**

### **1. Arquitectura del Módulo**

El script `osint_discord_forensics.py` implementará:

- **Extracción de información de usuarios:**
  - ID, nombre de usuario, discriminador, avatares históricos, flags de usuario.
  - Ejemplo: `user = await client.fetch_user(user_id)`.
- **Extracción de información de servidores:**
  - Fecha de creación del banner, miembros públicos, roles, canales públicos.
  - Ejemplo: `guild = await client.fetch_guild(guild_id)`.
- **Extracción de metadatos de invitaciones:**
  - Fecha de creación, creador, permisos, código de invitación.
  - Ejemplo: `invite = await client.fetch_invite(invite_link)`.
- **Manejo de rate limits:**
  - Implementar retrasos entre solicitudes para evitar bloqueos.
  - Usar `discord.utils.sleep_until` para manejar los límites de la API.

**Ejemplo de salida esperada:**

```json
{
  "user_id": "1234567890",
  "username": "EjemploUsuario",
  "discriminator": "1234",
  "avatar_history": [
    {
      "avatar_url": "https://cdn.discordapp.com/avatars/1234567890/...",
      "created_at": "2023-01-01T00:00:00"
    }
  ],
  "flags": ["HYPESQUAD_BRAVERY", "HYPESQUAD_BRILLIANCE"],
  "guild_info": {
    "guild_id": "9876543210",
    "name": "EjemploServidor",
    "created_at": "2022-01-01T00:00:00",
    "banner_url": "https://cdn.discordapp.com/banners/9876543210/..."
  }
}
```

### **2. Integración con Discord**

El comando `/audit_discord [User_ID o Invite_Link]` en Discord:

1. Recibirá un ID de usuario o un enlace de invitación como argumento.
2. Ejecutará el módulo `osint_discord_forensics.py` para extraer la información.
3. Devolverá un embed con los resultados estructurados.

**Ejemplo de uso:**

```bash
/audit_discord 1234567890
```

o

```bash
/audit_discord https://discord.gg/invite_link
```

**Resultado en Discord:**

```
🔍 Resultado de Forensics de Discord para 'EjemploUsuario':
- **ID:** 1234567890
- **Nombre:** EjemploUsuario#1234
- **Avatar Actual:** [Enlace]
- **Último Avatar:** [Enlace] (2023-01-01)
- **Flags:** Hypesquad (Bravery, Brilliance)
- **Servidor:** EjemploServidor (Creado: 2022-01-01)
```

---

## **Impacto Esperado**

### **Beneficios**

✅ **Extracción de metadatos forenses:** Información detallada de usuarios y servidores.
✅ **Uso seguro de la API:** Respetando los rate limits y términos de servicio de Discord.
✅ **Integración con Discord:** Comando fácil de usar para extraer información.
✅ **Protección del token:** Manejo seguro de credenciales y límites de la API.

### **Riesgos**

⚠ **Rate limits:** Requiere manejo cuidadoso para evitar bloqueos.
⚠ **Dependencia de Discord:** Cambios en la API podrían afectar el módulo.
⚠ **Información pública:** Solo debe extraerse información accesible públicamente.

---

## **Próximos Pasos**

1. **Aprobación de la propuesta** (esperando comando `opsx apply`).
2. **Implementación del módulo** (`osint_discord_forensics.py`).
3. **Integración con el bot de Discord**.
4. **Pruebas y validación** del flujo completo.

---

**Nota:** Este cambio sigue el protocolo OPSX y requiere aprobación explícita antes de aplicar modificaciones al código base.

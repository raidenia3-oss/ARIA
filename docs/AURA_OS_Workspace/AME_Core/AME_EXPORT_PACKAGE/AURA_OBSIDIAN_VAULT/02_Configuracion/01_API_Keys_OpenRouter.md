# Configuración de API Keys en OpenRouter

Este documento describe cómo configurar las API Keys gratuitas en OpenRouter para su uso con el ecosistema AURA/AME.

## 🔑 Obtención de API Keys

1. **Regístrate en OpenRouter**:
   - Visita [OpenRouter](https://openrouter.ai/) y crea una cuenta.

2. **Obtén tu API Key**:
   - Una vez registrado, ve a la sección de "API Keys".
   - Genera una nueva API Key con permisos de acceso a los modelos disponibles.

## 🛠 Configuración en el Ecosistema AURA/AME

### 1. Configuración del Servidor Central

El servidor central (`core/server.py`) utiliza las API Keys de OpenRouter para interactuar con los modelos de lenguaje.

#### Variables de Entorno

Configura las siguientes variables de entorno en el servidor central:

| Variable             | Descripción                           |
| -------------------- | ------------------------------------- |
| `OPENROUTER_API_KEY` | API Key de OpenRouter.                |
| `OPENROUTER_MODEL`   | Modelo predeterminado (ej: `llama3`). |

Ejemplo de configuración:

```bash
export OPENROUTER_API_KEY="tu_api_key_aqui"
export OPENROUTER_MODEL="llama3"
```

### 2. Configuración en el Archivo de Configuración

El archivo `config.json` en la raíz del proyecto puede contener configuraciones adicionales para las API Keys:

```json
{
  "openrouter": {
    "api_key": "tu_api_key_aqui",
    "default_model": "llama3",
    "models": [
      {
        "name": "llama3",
        "provider": "openrouter",
        "max_tokens": 4096
      },
      {
        "name": "mistral",
        "provider": "openrouter",
        "max_tokens": 8192
      }
    ]
  }
}
```

### 3. Configuración en las Apps Móviles

Las aplicaciones móviles (App Maid y APK AME) también pueden utilizar las API Keys de OpenRouter.

#### Configuración en `capacitor.config.ts`

```typescript
server: {
  androidScheme: 'https',
  url: 'https://tu-tunel-cloudflare.com',
  cleartext: true
},
api: {
  openrouter: {
    apiKey: 'tu_api_key_aqui',
    defaultModel: 'llama3'
  }
}
```

## 🔄 Rotación de API Keys

Para mantener la seguridad, se recomienda rotar las API Keys periódicamente.

1. **Genera una nueva API Key** en OpenRouter.
2. **Actualiza la configuración** en todos los componentes del ecosistema.
3. **Reinicia los servicios** para aplicar los cambios.

## 📌 Notas Importantes

- **Seguridad**: Nunca compartas tus API Keys en repositorios públicos o en configuraciones accesibles.
- **Uso legítimo**: Las API Keys deben usarse solo para fines legítimos y de acuerdo con los términos de servicio de OpenRouter.
- **Enlaces relacionados**:
  - [[01_Arquitectura/02_Proxy_FastAPI]]
  - [[02_Configuracion/02_IP_Local_Celular]]
  - [[02_Configuracion/03_Instalacion_Termux]]

## 🔗 Enlaces Relacionados

- [[01_Arquitectura_General]]
- [[02_Proxy_FastAPI]]
- [[03_Nodo_Termux]]

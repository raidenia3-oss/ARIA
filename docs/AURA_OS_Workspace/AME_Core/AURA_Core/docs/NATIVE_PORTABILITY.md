# AURA - Native Portability Guide (Dioxus-style)

> Cómo la API FastAPI actual puede ser consumida por una app nativa de escritorio en Rust/Dioxus, sin reescribir el backend.

---

## 1. Contrato de Backend (API-first)

AURA expone REST + JSON sobre HTTP. Eso es suficiente para cualquier cliente nativo (Rust, Swift, Kotlin, TypeScript).

### Endpointsbase

| Método | Ruta            | Body                                            | Respuesta                                            |
| ------ | --------------- | ----------------------------------------------- | ---------------------------------------------------- |
| `POST` | `/chat`         | `{ message, session_id?, provider?, persona? }` | `{ session_id, response, provider_used, intention }` |
| `POST` | `/agent-debate` | `{ topic }`                                     | `{ ok, topic, transcript, final_report }`            |
| `POST` | `/swarm-review` | `{ input_data }`                                | `{ ok, report_md }`                                  |
| `POST` | `/ingest-text`  | `{ text, source? }`                             | `{ status, doc_id, chunks }`                         |
| `GET`  | `/health`       | —                                               | `{ status, providers }`                              |

### Reglas

- Todo error HTTP >= 400 es JSON: `{"error": "..."}`
- UTF-8, fechas ISO-8601
- MIME: `application/json`
- CORS abierto (`*`) para desarrollo local.

---

## 2. Mapa de Tipos JSON → Rust (Dioxus)

```rust
// Ejemplo de tipos que el cliente Dioxus debería manejar
#[derive(Deserialize)]
pub struct ChatRequest {
    pub message: String,
    pub session_id: Option<i64>,
    pub persona: Option<String>,
}

#[derive(Deserialize)]
pub struct AgentDebateRequest {
    pub topic: String,
}

#[derive(Deserialize)]
pub struct SwarmReviewRequest {
    pub input_data: String,
}

#[derive(Deserialize)]
pub struct HealthResponse {
    pub status: String,
    pub providers: std::collections::HashMap<String, ProviderStatus>,
}

#[derive(Deserialize)]
pub struct ProviderStatus {
    pub status: String,
    pub latency_s: Option<f64>,
}
```

---

## 3. Cliente HTTP mínimo (Rust + reqwest)

```rust
use reqwest::Client;

pub struct AuraClient {
    base: String,
    client: Client,
}

impl AuraClient {
    pub fn new(base: impl Into<String>) -> Self {
        Self { base: base.into(), client: Client::new() }
    }

    pub async fn chat(&self, req: ChatRequest) -> Result<ChatResponse, reqwest::Error> {
        let url = format!("{}/chat", self.base);
        let res = self.client.post(&url).json(&req).send().await?;
        res.json().await
    }

    pub async fn agent_debate(&self, topic: impl Into<String>) -> Result<AgentDebateResponse, reqwest::Error> {
        let url = format!("{}/agent-debate", self.base);
        let body = AgentDebateRequest { topic: topic.into() };
        let res = self.client.post(&url).json(&body).send().await?;
        res.json().await
    }
}
```

---

## 4. Dioxus UI (conceptual)

```rust
use dioxus::prelude::*;

#[component]
fn App() -> Element {
    let mut messages = use_signal(Vec::new);
    let input = use_signal(String::new);

    let send = move |_| {
        let text = input().clone();
        if text.is_empty() { return; }
        messages.push((text.clone(), "user"));
        // Llamar a AURA API:
        // AuraClient::new("http://localhost:8000")
        //     .chat(ChatRequest { message: text, ..Default::default() })
        //     .await ...
    };

    rsx! {
        div { class: "chat",
            for (msg, role) in messages.iter() {
                div { class: format!("msg {role}"), "{msg}" }
            }
            input { oninput: move |e| input.set(e.value()), placeholder: "Pregunta a AURA..." }
            button { onclick: send, "Enviar" }
        }
    }
}
```

---

## 5. Migración futura (pasos)

1. **Estado actual**: FastAPI backend + React frontend (Docker Compose)
2. **Paso 1**: Levantar backend en modo producción: `docker compose up -d`
3. **Paso 2**: Crear un cliente Rust (`AuraClient`) contra `http://localhost:8000`
4. **Paso 3**: Empaquetar Dioxus app con Tauri o como binary nativo (no requiere cambiar el backend)
5. **Paso 4 (opcional)**: Reemplazar frontend React por Dioxus cuando la API sea 100% estable.

---

## 6. Ventajas de este enfoque

- **Sin reescritura**: El backend no cambia, solo se consume por HTTP.
- **Tipos compartidos**: Los JSON schemas son el contrato común.
- **Multi-frontend**: El mismo backend sirve a React (web) y a Dioxus (desktop).
- **Portabilidad total**: Rust + Dioxus corre en Windows, Linux, macOS sin Docker.

---

**AURA Engineering** | API-first | Listo para Dioxus/Tauri desktop.

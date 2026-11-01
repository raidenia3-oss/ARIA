# Memoria de ARIA en SQLite (5 capas + FTS5)

Documento de referencia del modulo de memoria. Todo vive **en el proceso de
ARIA**: SQLite de la biblioteca estandar, sin servidor, sin puerto, sin red.

- Codigo: `ARIA_APP/memory/sqlite_adapter.py`
- Integracion (hooks y API): `ARIA_APP/aria_va_core.py`
- Ventana "Memoria": `ARIA_APP/desktop_ui.py` (clase `MemoryPanel`, atajo `Ctrl+M`)
- Tests: `tests/test_memory_sqlite_adapter.py`, `tests/test_memory_panel_ui.py`,
  `tests/test_memory_session.py`

## Como se enciende

Apagada por defecto. Con la variable de entorno:

```
ARIA_MEMORY_SQLITE=true
```

Tambien se puede encender en caliente desde la ventana Memoria (boton
"Encender memoria"): es un interruptor de proceso, no un reinicio.

Con la memoria apagada no se crea ni el archivo de la base: `retain()` devuelve
`None` y `recall()` devuelve `[]`. ARIA se comporta exactamente igual que antes.

## Las cinco capas

| Capa | Que guarda | Confianza por defecto |
|---|---|---|
| `reglas` | Lo que el usuario fija. Solo se edita a mano. | `usuario` |
| `hechos` | Cosas comprobables. | `sistema` |
| `experiencias` | Lo que ARIA hizo y salio bien o mal. | `sistema` |
| `observaciones` | Lo que ARIA va notando. Sube de evidencia cada vez que se repite. | `sistema` |
| `modelos` | Resumenes: lo que se repite hasta ser un patron. | `sistema` |

Confianzas admitidas: `usuario`, `sistema`, `web`. Lo que no este en la lista
se degrada a la de la capa.

## Recuerdos de sesion (volatiles)

Aparte de las cinco capas, ARIA tiene un **recuerdo de sesion**: una lista en
RAM que vive mientras el proceso esta vivo y desaparece al cerrar ARIA.

- No depende del flag `ARIA_MEMORY_SQLITE`: funciona con la memoria
  persistente apagada.
- Tope de 200 recuerdos (sale lo mas viejo).
- Van primero en el `recall`: lo que el usuario acaba de decir pesa mas que
  lo de hace semanas.
- En la ventana Memoria, el filtro "Sesion (volatil)" los muestra, y hay
  botones para anadir uno ("Recordar (sesion)") y para vaciarlos.

En el chat, "recuerda <algo>" / "apunta <algo>" / "anota <algo>" guarda el
texto: como recuerdo de sesion siempre, y como hecho del usuario tambien
cuando la memoria persistente esta encendida.

```python
memory_session_add(texto, capa="observaciones")   # id, o None
memory_session_list()                              # del mas nuevo al mas viejo
memory_session_borrar(id_)
memory_session_clear()                             # devuelve cuantos habia
```

## Alta manual e importacion

- **Alta manual**: se puede escribir una entrada a mano desde la ventana
  Memoria (capa y confianza elegibles) y guardarla.
- **Importacion**: desde "Importar" se elige un archivo local `.json`, `.jsonl`
  o `.txt`; desde "Importar charlar" se importa el historial de
  `conversations.jsonl` como experiencias. Un JSON puede ser una lista de
  objetos o `{"entries": [...]}`; en JSONL se acepta un objeto por linea
  (reconoce `user`/`aria`) o texto plano. Lo que no se puede guardar
  (vacio o con credenciales) va a "omitidas"; lo que ya estaba en esa capa
  va a "duplicadas" (reimportar el mismo archivo no duplica nada).

```python
memory_agregar(texto, capa="hechos", fuente="usuario", confianza="usuario")
memory_importar(entradas)          # lista de dicts {'texto', 'capa', ...}
memory_importar_archivo(ruta)      # {'importadas': n, 'omitidas': m, 'duplicadas': d, 'error': None}
memory_importar_conversaciones()   # el conversations.jsonl de ARIA
```

## Como funciona

- **Dual-write**: el JSONL de siempre (`ARIA_APP/data/memory/conversations.jsonl`)
  sigue siendo la fuente de verdad. SQLite es una copia consultable al lado.
- **Indice FTS5** con BM25 para ordenar por relevancia. Cada documento del
  indice tiene su propio espacio de nombres (`mem_map`), porque cada capa
  reinicia sus ids.
- **Filtro anti-secreto**: lo que huele a credencial (passwords, tokens, claves,
  JWT, claves SSH) no se guarda, ni siquiera en local.
- **Consolidacion sin LLM** (`reflect`): una observacion con evidencia >= 3 se
  promueve a `modelos` ("Patron observado N veces: ...") y queda consolidada.
  Corre cada 25 escrituras, en segundo plano.
- **Consulta segura**: los signos raros de una pregunta (? ! - ( ) ") dejan de
  ser sintaxis FTS y se buscan como texto. Las palabras se unen con OR y el
  BM25 deja arriba lo que de verdad encaja.
- **Las reglas llegan al cerebro**: lo que el usuario fija en la capa `reglas`
  se mete en el prompt del modelo local ("Reglas del usuario: ..."). Con la
  memoria apagada el prompt es exactamente el de antes. El estado del sistema
  dice cuantas reglas hay activas.

## API

Desde `aria_va_core` (o desde el nucleo VA, con los mismos nombres):

```python
memory_retain(texto, tipo="observaciones", fuente="sistema", confianza="sistema")
memory_recall(consulta, k=5)        # busqueda FTS5 (+ recuerdos de sesion)
memory_reflect()                     # consolida observaciones repetidas
memory_listar(capa="", limite=50)    # entradas de una capa o de todas
memory_borrar(capa, id_)             # 'sesion' borra un recuerdo volatil
memory_fijar(texto)                  # va a la capa 'reglas'
memory_exportar()                    # todo, para guardar en JSON
memory_conteo()                      # cuantas entradas hay en cada capa
set_memory_enabled(True | False | None)   # interruptor en caliente
```

El `VAAdapter` de la interfaz expone lo mismo por tipo de peticion:
`memory_list`, `memory_recall`, `memory_borrar`, `memory_fijar`,
`memory_reflect`, `memory_export`, `memory_toggle`, `memory_add`,
`memory_import`, `memory_session_add`, `memory_session_list`,
`memory_session_clear`.

## La ventana Memoria

`Ctrl+M` o el boton del encabezado. Permite:

- Ver por capa (o todas) y ver cuantas hay en cada una.
- Buscar (FTS5).
- Escribir y guardar una entrada a mano (capa y confianza elegibles).
- Fijar una entrada como regla.
- Borrar una entrada (incluidas las de sesion).
- Consolidar (promover observaciones repetidas a modelos).
- Exportar a JSON.
- Importar un archivo de memoria o el historial de conversaciones.
- Anadir un recuerdo de sesion y vaciar la sesion.

## Donde vive el archivo

En desarrollo: `ARIA_APP/data/memory/aria_mem.db` (mas sus `-wal` y `-shm`).
Se puede mover con la variable `ARIA_MEMORY_DB` (util en pruebas).

En el EXE empaquetado (PyInstaller) la carpeta de trabajo es temporal y se
borra al cerrar, asi que la base va a
`%LOCALAPPDATA%/ARIA_OS/data/memory/aria_mem.db` y sobrevive a los reinicios.
El adaptador se carga por ruta: por eso el build lo copia dentro del EXE
(`--add-data "AURA_APP\memory\sqlite_adapter.py;memory"`).

## Rendimiento

Medido en 10.000 entradas (con los indices de texto de las 5 capas):

- insercion: ~6.9 s (10k filas, con WAL y `synchronous=NORMAL`)
- `recall` de una frase: p50 14.8 ms / p95 19.9 ms
- `recall` de coincidencia exacta: p50 < 1 ms
- `recall` de frase (10 resultados): p50 11.7 ms
- base: ~4.3 MB (+ indices de dedupe)

## Pruebas

```
.venv\Scripts\python.exe -m pytest tests/test_memory_sqlite_adapter.py tests/test_memory_panel_ui.py tests/test_memory_session.py tests/test_memory_layers.py -q
```

Los tests escriben siempre en una base temporal (`ARIA_MEMORY_DB`), nunca en la
de ARIA.

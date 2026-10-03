# STATUS — airi_mobile (Dart/Flutter)

## NO VERIFICADO

Este modulo **nunca ha pasado `flutter analyze` ni `flutter test`**. No hay Flutter
ni Dart SDK instalados en la maquina de desarrollo, y en el repo no hay lockfile
resuelto ni output de analisis que sirva como evidencia.

## Defecto conocido en `lib/models/pc_state.dart`

`SystemStatus.fromJson` **fabrica datos** en vez de reportar lo no medido:

- `port` -> `8002` literal
- `version` -> `'0.0.0'` literal
- `status` / `framework` -> `'unknown'`
- `mode` -> `''`
- contadores (`requests_served`, etc.) -> `0` via `_toInt(...)`

Esto viola la regla declarada en el propio fichero (lineas 32-35): un dato no
medido debe ser `null` con `data_source: "unavailable"`, no un literal.

Ademas hay **37 ocurrencias de `??`** mientras los campos son **no-nullables**
(`final String status; final int port; ...`), es decir, defaults silenciosos
escondidos en el parser.

`MemoryInfo` y `VolumeInfo` si estan corregidos (campos nullable + `_notMeasured`).
`SystemStatus` no.

## Contrato a cumplir en Phase C

1. Sustituir cada literal fabricado por `null` + `data_source`.
2. Tipos de campo nullable donde el servidor no puede garantizar el dato.
3. Ejecutar y adjuntar al PR la salida real de:
   - `cd v6\airi_mobile; flutter pub get`
   - `flutter analyze`
   - `flutter test test\pc_state_test.dart`

Hasta que eso pase, **el frontend mobile no debe considerarse parte de un release
verificado**. El tag `v6.0-backend` cubre solo el backend; el estado real de este
modulo es el de este fichero.
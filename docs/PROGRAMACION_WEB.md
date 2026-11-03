# Programación orientada a la Web en el predictor

Este documento explica tres decisiones de arquitectura web del proyecto:

1. **Patrones de rendering**: el frontend es Next.js 16 con App Router y usa SSG, ISR, SSR y CSR, cada uno donde corresponde.
2. **gRPC**: el modelo predictivo vive en un motor gRPC en Python que usa los cuatro tipos de RPC. FastAPI es su cliente y lo conecta al navegador con JSON, SSE y WebSocket.
3. **Web Workers**: las tareas pesadas del navegador corren en hilos aparte.

```
Navegador ──HTML (SSG/ISR/SSR)──► Next.js en Vercel ──fetch desde el servidor──┐
    │                                                                         ▼
    ├── JSON · SSE · WebSocket ──────────────────────────────────► FastAPI en Render (público)
    │                                                                         │ gRPC sobre HTTP/2 (127.0.0.1)
    └── Web Workers (CSV, matriz de sensibilidad)                             ▼
                                                                 Motor de predicción (Python)
                                                                              │
                                                                     PostgreSQL (Neon)
```

---

## 1. Patrones de rendering

| Patrón | Página | Configuración en Next.js | Por qué |
|---|---|---|---|
| **SSG** | `/enfermedades`, `/enfermedades/[codigo]`, `/metodologia`, `/patrones` | `dynamic = "force-static"`, `generateStaticParams`, `dynamicParams = false` | Contenido editorial que no cambia con los datos semanales: se genera una vez en el build y se sirve desde la CDN |
| **ISR** | `/`, `/municipio/[id]` | `revalidate = 3600`, `generateStaticParams`, `revalidatePath` | Muchas visitas y datos que cambian una vez al día. Se sirve estático y se regenera cuando el backend avisa |
| **SSR** | `/alertas`, `/reportes` | `dynamic = "force-dynamic"`, `searchParams`, `headers()` | Los resultados dependen de los filtros de cada visita; cada búsqueda es una URL compartible ya renderizada |
| **CSR** | `/mapa`, `/simulador`, `/admin`, `/farmacia`, `/login` | `"use client"`, `next/dynamic` con `ssr: false` | Leaflet necesita `window`; el simulador conversa por WebSocket; los paneles dependen del token del usuario |

### Cómo se pide la información en cada caso

`frontend/src/lib/servidor.ts` centraliza el `fetch` del servidor. En cada página la estrategia de caché se nota en el código:

```ts
pedir("/enfermedades", {}, { cache: "force-cache" });                       // SSG: una vez, en el build
pedir("/dashboard/resumen", { municipio_id }, { revalidar: 3600 });         // ISR: como máximo cada hora
pedir("/alertas/buscar", filtros, { cache: "no-store" });                   // SSR: en cada visita
dashboardApi.riesgoMunicipios();                                            // CSR: Axios desde el navegador
```

### ISR con revalidación bajo demanda

El tablero de cada municipio se genera en el build: hay un HTML por cada municipio activo. Después se regenera de tres formas:

- **Por tiempo**: `revalidate = 3600`. La primera visita después de una hora recibe la versión anterior y dispara la regeneración en segundo plano.
- **Desde el backend**: al terminar el cron diario o un reentrenamiento, `revalidar_frontend()` llama a `POST /api/revalidar` con el secreto `REVALIDAR_SECRET`. Ese Route Handler ejecuta `revalidatePath("/municipio/[id]", "page")`.
- **Desde el panel de la página**: el botón «Revalidar ahora» usa una Server Action (`app/acciones.ts`).

Si la API falla durante una regeneración, Next.js sigue sirviendo la versión anterior. Si falla durante el build (Render dormido), ocurre lo siguiente:

- `scripts/despertar-api.mjs` intenta despertar la API durante 2,5 minutos.
- Si no responde, la portada se genera en una versión de respaldo que se auto-revalida con el primer visitante.
- Los tableros se generan en su primera visita (`dynamicParams = true`).

### El tablero no hace peticiones al interactuar

La página ISR pide en paralelo todas las enfermedades y cinco años de semanas (`lib/tablero.ts`). Esos datos se pasan como props al componente de cliente `TableroMunicipio`:

- Cambiar de enfermedad o de rango de tiempo solo filtra datos que ya están en el navegador.
- Cambiar de municipio navega a otra página estática, que `next/link` precarga.

### Panel del patrón y comparativa

Cada página muestra arriba un `RenderPanel` con:

- el patrón;
- la hora en que se generó el HTML y su antigüedad;
- la ventana de ISR;
- el TTFB de la carga;
- el porqué de la elección.

El panel también escribe `data-render-generado` en el HTML. La página `/patrones` pide una página de cada patrón tres veces desde el navegador y compara TTFB, tamaño, si el HTML trae datos, la hora escrita en el HTML y la cabecera `x-vercel-cache`. Así se ve la diferencia en la práctica:

- en SSG la hora no cambia;
- en ISR cambia solo al regenerar;
- en SSR cambia siempre;
- en CSR el HTML llega sin datos.

### Componentes de servidor y de cliente

Componentes de servidor:

- el layout raíz, que incluye el script de tema antes de pintar;
- todas las páginas.

Componentes de cliente:

- la cabecera (depende de la sesión);
- el banner de alertas (SSE);
- los gráficos (Recharts);
- el mapa (Leaflet);
- los formularios.

El tema se lee al montar para que el HTML del servidor y el primer render del cliente coincidan (sin errores de hidratación).

---

## 2. Motor de predicción gRPC

### Por qué un motor aparte

Deserializar un modelo y construir el dataset cuesta cientos de milisegundos, y la API REST lo pagaba en cada petición. El motor es un proceso de larga vida:

- Guarda en memoria un `Pronosticador` por enfermedad (`motor/cache.py`). Lo invalida cuando cambia el modelo activo o vence el TTL.
- Expone el modelo con un contrato tipado (`prediccion.proto`).

El cálculo es exactamente el mismo que usa el servicio que guarda las predicciones: `ml/pronostico.py` es una función pura compartida por los dos.

### Los cuatro tipos de RPC

| Tipo | RPC | Qué hace | Puente hacia el navegador |
|---|---|---|---|
| Unary | `Estado`, `Predecir` | Versión, modelos en memoria; pronóstico al momento | `GET /motor/estado`, `GET /motor/pronostico` → JSON |
| Server streaming | `Entrenar` | Cada candidato, el modelo ganador, las predicciones y las alertas, con porcentaje | `POST /motor/entrenar` → **SSE** (se lee con `fetch` porque lleva el token) |
| Server streaming | `SeguirAlertas` | Alertas activas y luego cada alerta NUEVA, ACTUALIZADA o CERRADA | `GET /motor/alertas/eventos` → **SSE** (`EventSource`) |
| Client streaming | `CargarReportesFarmacia` | La farmacia envía su histórico fila por fila; el motor valida al llegar y responde un resumen | `POST /motor/farmacia/carga` → stream de filas |
| Bidireccional | `SimularEscenarios` | Escenarios «¿qué pasa si…?»: por cada uno, el pronóstico modificado | **WebSocket** `/motor/simulador` ↔ stream |

### Por qué el navegador no habla gRPC directamente

Hay dos razones:

- Los navegadores no permiten manejar HTTP/2 con *trailers*, que es como gRPC envía el estado final.
- Render (plan gratis) solo publica un puerto HTTP.

Por eso el motor escucha en `127.0.0.1:50051` y FastAPI es su único cliente. FastAPI traduce cada tipo de RPC al mecanismo web equivalente, como en el taller de catación.

### Detalles de implementación

- **Contrato**: `backend/app/motor/protos/prediccion.proto` incluye enums (`NivelRiesgo`, `Etapa`, `Tipo`), campos `optional` y mensajes anidados. El código se genera con `scripts/generar_grpc.sh` y el CI verifica que esté al día con el `.proto`.
- **Servidor** (`servidor.py`):
  - pool de hilos con `maximum_concurrent_rpcs`, para que por encima del límite responda `RESOURCE_EXHAUSTED` en lugar de dejar peticiones colgadas;
  - keepalive para los streams largos;
  - `grpc.health.v1` y reflexión (`grpcurl -plaintext 127.0.0.1:50051 list`);
  - apagado ordenado con SIGTERM.
- **Interceptores** (`interceptores.py`):
  - token compartido en el metadato `authorization`;
  - registro de método, código y duración.

  Los dos envuelven el *handler* con uno del mismo tipo, así sirven para las cuatro clases de RPC.
- **Metadatos**: la carga de farmacias envía el usuario en `x-actor-id`. El motor aplica las mismas reglas que el formulario semanal (farmacia propia, solo las últimas 8 semanas).
- **Errores** (`errores.py`): las excepciones de dominio se convierten en códigos gRPC y luego en HTTP.

  | Dominio | gRPC | HTTP |
  |---|---|---|
  | `NoEncontradoError` | `NOT_FOUND` | 404 |
  | `ConflictoError` | `ABORTED` | 409 |
  | `ReglaNegocioError` | `FAILED_PRECONDITION` | 422 |
  | Motor apagado | `UNAVAILABLE` | 503 |

  En el stream bidireccional, un escenario inválido vuelve con el campo `error` y el stream sigue vivo.
- **Entrenar** (server streaming): el entrenamiento corre en su hilo y deja cada `EventoProgreso` en una cola que el generador vacía hacia el stream. `ControlEntrenamiento` impide dos entrenamientos a la vez. El cliente lee el primer mensaje antes de abrir el SSE, para que un 409 llegue como respuesta HTTP normal.
- **SeguirAlertas** (server streaming): un único hilo (`DifusorAlertas`, publicador/suscriptor) compara las alertas activas con la foto anterior y reparte las diferencias en la cola de cada suscriptor. Cancelar el stream libera la suscripción.
- **SSE**:
  - comentario `: keepalive` cada 15 s para que los proxies no corten;
  - `retry: 5000`;
  - evento `fallo` (no `error`, que es el evento nativo de `EventSource`) cuando el motor no responde. El navegador pasa entonces a consultar cada 5 minutos.
- **WebSocket**: dos tareas concurrentes, una que sube escenarios y otra que baja resultados.
- **Despliegue** (`start.sh`): migraciones y seed, motor en segundo plano con un bucle que lo reinicia si se cae, espera del chequeo de salud y uvicorn como proceso principal. Si el motor no está, la API sigue funcionando y los endpoints `/motor` responden 503.

### Pruebas

- `tests/test_motor.py` levanta el servidor real en un puerto libre y prueba los cuatro tipos de RPC, el token, la salud, la caché, la cancelación de streams y las reglas de negocio.
- `tests/test_motor_api.py` prueba el puente: JSON, SSE, la carga y el WebSocket, y también el motor apagado.

---

## 3. Web Workers

| Worker | Lo usa | Qué hace fuera del hilo principal |
|---|---|---|
| `workers/csv.worker.ts` | Administración (carga de datos) y Farmacia (carga masiva) | Decodifica el archivo (UTF-8 o Windows-1252), lo recorre con un lector RFC 4180 y valida cada fila con las mismas reglas del backend. Informa el avance y devuelve errores por fila, vista previa, periodo, totales, grupos, filas normalizadas y un CSV limpio |
| `workers/sensibilidad.worker.ts` | Simulador | Abre su propio WebSocket al simulador, envía los 49 escenarios de una grilla (p. ej. lluvia × búsquedas), recibe y agrega las respuestas por id y devuelve la matriz para pintarla como mapa de calor |

### Diseño

- **Protocolo tipado**: `workers/*/mensajes.ts` define los mensajes de ida y vuelta. Lo usan los dos lados.
- **Lógica pura y separada**: `workers/csv/analizar.ts` no sabe que corre en un worker.
- **Hooks** (`useAnalizadorCsv`, `useMatrizSensibilidad`):
  - crean el worker con `new Worker(new URL("…", import.meta.url), { type: "module" })`, que Next.js empaqueta como archivo aparte;
  - lo terminan al desmontar;
  - convierten los mensajes en una promesa o en estado;
  - ignoran respuestas de trabajos cancelados.

  Cancelar un análisis termina el worker y crea uno nuevo; no hay forma más rápida de detener un cálculo en otro hilo.
- **Evidencia**: mientras un worker trabaja, la interfaz muestra los **fps del hilo principal** (`useFps`, con `requestAnimationFrame`). Siguen altos, porque la página no se congela.
- **Validación en el navegador**: el servidor nunca confía solo en el cliente. La importación y el motor validan otra vez todo lo que llega.

---

## Cómo verlo funcionando

```bash
# Backend + motor (dos terminales, o sh start.sh)
cd backend && python -m app.motor.servidor
cd backend && uvicorn app.main:app --reload

# Frontend en modo producción (en `npm run dev` todo se renderiza por petición)
cd frontend && npm run build && npm start
```

Qué probar:

1. Abre `/patrones` y pulsa «Medir los 4 patrones».
2. Abre `/mapa` y, en otra pestaña, reentrena desde `/admin` → Modelo: el avance llega en vivo y el mapa recibe los cambios de alertas sin recargar.
3. En `/simulador` mueve los controles y calcula la matriz de sensibilidad.
4. En `/admin` → Fuentes de datos o en `/farmacia`, elige un CSV grande.

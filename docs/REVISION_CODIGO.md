# Revisión de código en 5 rondas

Revisión profunda del predictor (backend FastAPI y frontend React) buscando código limpio, patrones de diseño y estructuras de datos adecuadas. Cada ronda tiene su propia rama `refactor/ronda-N-…` con commits pequeños y se integró a `main` con un *merge*. El comportamiento visible no cambió: las pruebas pasaron después de cada ronda y se agregaron pruebas nuevas para lo que se tocó.

| | Antes | Después |
|---|---|---|
| Pruebas automáticas | 76 | 89 |
| Hallazgos de `ruff` con la configuración de la ronda 5 | 137 | 0 |
| Consultas SQL de `GET /dashboard/riesgo-municipios` | 75 | 15 |
| Consultas SQL de una evaluación de alertas | 107 | 16 |
| Consultas SQL del CSV de predicciones | 30 | 10 |
| Consultas SQL del PDF de un municipio | 47 | 27 |

Las consultas se midieron con un contador de eventos de SQLAlchemy sobre la base de demostración (6 municipios, 4 enfermedades, 7 años de semanas).

---

## Ronda 1 · Duplicación (DRY)

**Hallazgos**

- La misma línea `[t.strip() for t in texto.split(",") if t.strip()]` estaba copiada en 6 lugares (servicios de Trends, SIVIGILA, predicción, dataset, seed y esquemas), cada copia con pequeñas diferencias (unas pasaban a minúsculas, otras no).
- Tres funciones distintas escribían números con coma decimal (`_num` en predicción, explicador y reportes).
- Las etiquetas «Bajo / Moderado / Alto / Muy alto» y el orden de los niveles estaban en tres diccionarios distintos.

**Cambios**

- `app/core/texto.py`: `separar_lista()` y `numero_es()`, probadas una sola vez.
- *Modelo de dominio rico*: `Enfermedad` expone `lista_terminos`, `lista_codigos_sivigila`, `lista_categorias_farmacia` y `lista_recomendaciones`. El conocimiento de cómo se guardan esas columnas queda en la entidad, no repartido por los servicios.
- `NivelRiesgo` ahora sabe ordenarse (`rango`), nombrarse (`etiqueta`) y elegir el peor de una colección (`peor()`). Desaparecen `ORDEN_NIVELES`, `nivel_maximo()` y los diccionarios `TEXTO_NIVEL`.

## Ronda 2 · Estructuras de datos y consultas (N+1)

**Hallazgos**

- *Problema N+1*: el riesgo por municipio pedía la serie de casos con una consulta por cada par municipio × enfermedad, y otra más para el modelo y las predicciones de cada par.
- Las alertas y los reportes creaban sus propios servicios de dashboard y de predicción, así que repetían las mismas consultas.
- Los tres repositorios con «insertar o actualizar» tenían su propia copia del algoritmo. Uno de ellos hacía una consulta por cada pareja municipio-enfermedad; la importación de eventos hacía una consulta por fila del CSV.

**Cambios**

- `BaseRepository.upsert(filas, clave, alcance)`: una sola lectura de los registros existentes, indexados en un **diccionario por clave natural**, de modo que cada fila se resuelve en O(1). Los repositorios de clima, casos y búsquedas, y los importadores, lo reutilizan.
- `DashboardService` carga los casos de una enfermedad para **todos** los municipios en una consulta y los agrupa en `dict[municipio → dict[(año, semana) → casos]]`.
- `PrediccionService` guarda en memoria, durante la petición, el modelo activo de cada enfermedad y sus predicciones agrupadas por municipio (*memoización*). La caché se invalida al entrenar o predecir.
- Alertas y reportes comparten una sola instancia del servicio de predicción (*inyección de dependencias*).
- `tests/test_consultas.py` falla si el riesgo por municipio vuelve a hacer una consulta por municipio.

## Ronda 3 · Patrones y encapsulamiento

**Hallazgos**

- *Valores mágicos*: textos sueltos como `"OBSERVADO"`, `"PREDICHO"`, `"CAIDA_CENIZA"` y `"BOLETIN"`, cuando ya existían enums para casi todos.
- Unas clases llamaban métodos privados de otras: `dash._semana_referencia()`, `pred._ultimas()` y `modelo._preparar()`.
- *Estado global mutable*: el estado del reentrenamiento eran variables de módulo modificadas con `global` desde varios hilos.
- Varios `import` dentro de funciones para esquivar un import circular entre predicción y alertas.

**Cambios**

- Nuevo enum `OrigenAlerta` y propiedad `NivelRiesgo.es_alerta`. Repositorios, dataset, seed e importación usan `TipoEventoVolcanico`.
- API pública explícita: `semana_referencia()`, `ultimas_predicciones()` y `preparar()`.
- `app/services/entrenamiento.py`: la clase `ControlEntrenamiento` encapsula el estado compartido entre hilos, con un candado y una interfaz pequeña (`iniciar`, `terminar`, `estado`, `reiniciar`). `lanzar_en_hilo()` reemplaza las dos copias de «marcar inicio + crear hilo».
- La orquestación «entrenar → evaluar alertas» vive en ese módulo, así que el grafo de dependencias quedó sin ciclos y todos los imports volvieron al nivel superior.

## Ronda 4 · Frontend

**Hallazgos**

- El mismo grupo de botones (rango de tiempo, filtro de alertas, modo del mapa) estaba copiado en tres pantallas.
- El patrón `useEffect` + `useState` + `.then/.catch` se repetía en todas las vistas y tenía una **condición de carrera**: si el usuario cambiaba rápido de municipio, una respuesta vieja podía llegar tarde y pisar la nueva.
- Conversiones `as Nivel` innecesarias, y el orden de los niveles del semáforo repetido en tres componentes.

**Cambios**

- Hook `useDatos(cargar, deps)`: devuelve `{ datos, error, cargando, recargar }`, descarta las respuestas obsoletas y, al recargar, conserva los datos mientras llegan los nuevos (sin parpadeo). Se usa en el dashboard, en «¿Por qué?» y en los paneles de fuentes y alertas.
- Componente genérico `Segmentado<T>` y clase común `claseCabeceraTabla`.
- `ORDEN_NIVELES` y `rangoNivel()` en `lib/formato.ts`, sin conversiones de tipo.

## Ronda 5 · Linter, complejidad y código muerto

**Hallazgos** (con `ruff` y reglas de pyflakes, bugbear, pylint, complejidad, nombres, rendimiento y simplificación):

- *Closures que capturan la variable del bucle* (bugbear B023) en el adaptador de Open-Meteo, el dataset y el generador del seed. No eran bugs porque se usaban dentro de la misma vuelta, pero lo serían al primer cambio.
- `zip()` sin `strict`, que oculta listas de distinto largo.
- `resumen_pdf()` tenía 61 sentencias en un solo método (*long method*).
- La misma columna de clave foránea se repetía 11 veces en los modelos.
- Variables reasignadas dentro de su propio `for`, nombres con `ñ` en identificadores, excepción sin sufijo `Error`, una lambda llamada en el sitio, imports desordenados, `datetime.timezone.utc` antiguo, `# noqa` sin uso y líneas de más de 120 caracteres.

**Cambios**

- `backend/ruff.toml` documenta las reglas y sus excepciones justificadas. Por ejemplo, `Depends()` como argumento por defecto es idiomático en FastAPI y `X`/`y` es la convención de scikit-learn. El CI ejecuta `ruff check` en cada *push*.
- El PDF se arma con métodos por sección (patrón *Builder*): `_seccion_semaforo`, `_seccion_graficas`, `_seccion_alertas`, `_seccion_volcan` y `_seccion_modelos`. Los estilos se agrupan en `_Estilos`.
- `fk("municipios.id")` en `app/db/base.py` reemplaza la definición repetida de las claves foráneas. `alembic check` confirma que el esquema no cambió.
- Genéricos con la sintaxis de Python 3.12 (`class BaseRepository[ModelT: Base]`), `datetime.UTC` y nombres ASCII (`senales`).

---

## Cómo verificar

```bash
cd backend
ruff check app tests      # 0 hallazgos
pytest                    # 89 pruebas
cd ../frontend
npm run build             # tsc estricto + build
```

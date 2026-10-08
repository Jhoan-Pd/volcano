# CSV de respaldo de Google Trends

`pytrends` no es una API oficial de Google y puede fallar (HTTP 429, cambios de formato).
Cuando falla, `TrendsFuente` lee los `.csv` de esta carpeta (variable `TRENDS_CSV_DIR`).

Formatos aceptados:

1. **Exportación de trends.google.com** (`multiTimeline.csv`): entra a
   <https://trends.google.com/trends/explore?geo=CO-NAR&q=fiebre>, elige *Últimos 5 años*
   y usa el botón de descarga. Puedes dejar varios archivos; si se repite una semana gana
   el último archivo en orden alfabético.
2. **Formato largo propio**: `termino,fecha_semana,indice[,region][,es_simulado]`.

`trends_respaldo_narino.csv` es un respaldo **simulado** (columna `es_simulado=1`) generado
con `python -m app.seed.exportar_trends`. Sirve para que el sistema funcione sin internet;
reemplázalo por exportaciones reales cuando las tengas.

También puedes subir estos archivos desde *Administración → Datos y modelo → Importar CSV*.

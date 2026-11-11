# Google Trends fallback CSV files

`pytrends` is not an official Google API and can fail (HTTP 429, format changes). When it does,
`TrendsSource` reads the `.csv` files in this folder (`TRENDS_CSV_DIR`).

Accepted formats:

1. **trends.google.com export** (`multiTimeline.csv`): open
   <https://trends.google.com/trends/explore?geo=CO-NAR&q=fiebre>, pick *Past 5 years* and use the
   download button. Several files may live here; when a week repeats, the last file in
   alphabetical order wins.
2. **Long format**: `term,week_start,interest[,region][,is_simulated]` (the older Spanish headers
   `termino,fecha_semana,indice,es_simulado` are still accepted).

`trends_fallback_narino.csv` is a **simulated** fallback (`is_simulated=1`) generated with
`python -m volcano.seed.export_trends`. It lets the system run offline; replace it with real exports
when you have them. Long-format files can also be uploaded from *Administración → Fuentes de datos
→ Carga de CSV* (type «Búsquedas»).

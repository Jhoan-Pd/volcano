"""Datos maestros de la semilla.

Municipios: los 6 del sistema anterior (zona de influencia del Galeras), con el código
DIVIPOLA de La Florida corregido (52381; el dataset anterior traía 52299).
Población y distancia al cráter se reutilizan del sistema anterior; coordenadas y altitud
son las de la cabecera municipal (aprox.). El ADMIN puede corregirlas desde el panel.
"""

MUNICIPIOS = [
    {"codigo_divipola": "52001", "nombre": "Pasto", "latitud": 1.2136, "longitud": -77.2811,
     "altitud_m": 2527, "poblacion": 450000, "distancia_crater_km": 9},
    {"codigo_divipola": "52207", "nombre": "Consacá", "latitud": 1.2078, "longitud": -77.4661,
     "altitud_m": 1730, "poblacion": 14000, "distancia_crater_km": 15},
    {"codigo_divipola": "52381", "nombre": "La Florida", "latitud": 1.2972, "longitud": -77.4064,
     "altitud_m": 2160, "poblacion": 18000, "distancia_crater_km": 22},
    {"codigo_divipola": "52480", "nombre": "Nariño", "latitud": 1.2892, "longitud": -77.3594,
     "altitud_m": 2240, "poblacion": 22000, "distancia_crater_km": 25},
    {"codigo_divipola": "52683", "nombre": "Sandoná", "latitud": 1.2847, "longitud": -77.4711,
     "altitud_m": 1848, "poblacion": 30000, "distancia_crater_km": 18},
    {"codigo_divipola": "52885", "nombre": "Yacuanquer", "latitud": 1.1158, "longitud": -77.4014,
     "altitud_m": 2620, "poblacion": 13000, "distancia_crater_km": 16},
]

ENFERMEDADES = [
    {
        "codigo": "IRA", "categorias_farmacia": "ANTIGRIPALES,ANTIPIRETICOS", "nombre": "Gripe / Infección Respiratoria Aguda",
        "descripcion": "Infecciones de vías respiratorias (gripa, bronquitis, neumonía). Aumentan con el frío, "
                       "la humedad y las temporadas de lluvia.",
        "codigo_cie10": "J00-J22", "color": "#2a78d6",
        "terminos_busqueda": "gripa,tos,fiebre,dolor de garganta",
        "recomendaciones": "Lávate las manos con agua y jabón con frecuencia.\n"
                           "Usa tapabocas si tienes síntomas respiratorios y quédate en casa.\n"
                           "Abrígate en las noches frías y ventila los espacios cerrados.\n"
                           "Vacúnate contra la influenza (niños, mayores de 60 y gestantes).\n"
                           "Consulta de inmediato si hay dificultad para respirar o fiebre de más de 3 días.",
    },
    {
        "codigo": "EDA", "categorias_farmacia": "SALES_REHIDRATACION", "nombre": "Enfermedad Diarreica Aguda",
        "descripcion": "Diarrea de origen infeccioso. Se asocia a lluvias fuertes (contaminación de fuentes "
                       "de agua) y a temporadas secas (escasez de agua).",
        "codigo_cie10": "A00-A09", "color": "#1baf7a",
        "terminos_busqueda": "diarrea",
        "recomendaciones": "Hierve o desinfecta el agua de consumo.\n"
                           "Lava frutas y verduras y cocina bien los alimentos.\n"
                           "Lávate las manos antes de comer y después de ir al baño.\n"
                           "Ante diarrea, usa sales de rehidratación oral y no te automediques.\n"
                           "Consulta si hay sangre en las heces, vómito persistente o signos de deshidratación.",
    },
    {
        "codigo": "DENGUE", "categorias_farmacia": "REPELENTES,ANTIPIRETICOS", "codigos_sivigila": "210,220", "nombre": "Dengue",
        "descripcion": "Transmitido por el mosquito Aedes aegypti, que casi no sobrevive por encima de "
                       "~1.800 m s. n. m.; por eso el riesgo se concentra en Consacá y Sandoná y en casos "
                       "importados en Pasto.",
        "codigo_cie10": "A90-A91", "color": "#e87ba4",
        "terminos_busqueda": "dengue,fiebre",
        "umbral_amarillo_pct": 50, "umbral_naranja_pct": 75, "umbral_rojo_pct": 90,
        "recomendaciones": "Elimina recipientes con agua estancada (llantas, floreros, tanques destapados).\n"
                           "Usa repelente y ropa de manga larga si viajas a zonas cálidas.\n"
                           "Instala toldillos y mallas en puertas y ventanas.\n"
                           "Ante fiebre alta con dolor de cuerpo o detrás de los ojos, consulta y no tomes ibuprofeno ni aspirina.",
    },
    {
        "codigo": "RESP_CENIZA", "categorias_farmacia": "TAPABOCAS,INHALADORES", "nombre": "Afección respiratoria por ceniza volcánica",
        "descripcion": "Irritación de vías respiratorias, ojos y piel por caída de ceniza y gases (SO₂) del "
                       "Volcán Galeras. Afecta más a niños, adultos mayores y personas con asma o EPOC.",
        "codigo_cie10": "J68, J98.8", "color": "#4a3aa7",
        "terminos_busqueda": "ceniza volcán,tos",
        "recomendaciones": "Usa tapabocas N95 durante la caída de ceniza.\n"
                           "Cierra puertas y ventanas y evita actividades al aire libre.\n"
                           "Protege tanques y fuentes de agua de la ceniza.\n"
                           "Si tienes asma o EPOC, ten a mano tu inhalador y sigue tu plan de manejo.\n"
                           "Sigue los boletines del Servicio Geológico Colombiano y de la Gestión del Riesgo.",
    },
]

# Farmacias ficticias (no corresponden a establecimientos reales)
FARMACIAS = [
    ("Droguería Demo Centro", "Pasto"), ("Droguería Demo Norte", "Pasto"),
    ("Droguería Demo Consacá", "Consacá"), ("Droguería Demo La Florida", "La Florida"),
    ("Droguería Demo Nariño", "Nariño"), ("Droguería Demo Sandoná", "Sandoná"),
    ("Droguería Demo Yacuanquer", "Yacuanquer"),
]

# Último boletín REAL verificado (SGC) — el resto del histórico es simulado
BOLETIN_REAL = {
    "fecha_inicio": "2026-08-25", "fecha_fin": "2026-08-31", "nivel_actividad": "AMARILLO",
    "descripcion": "Alerta Amarilla: volcán activo con cambios en el comportamiento del nivel base de los "
                   "parámetros monitoreados. Pequeñas emisiones de gases blancos de baja altura; sin reporte "
                   "de caída de ceniza.",
    "url_boletin": "https://www2.sgc.gov.co/Noticias/boletinesDocumentos/"
                   "Boletin_semanal_de_actividad_del_volcan_galeras_del_25_al_31_de_agosto_de_2026.pdf",
}

# Calibración de casos semanales promedio (IRA/EDA) tomada de
# BI_Health_Nari-o/data/final/dataset_final_municipio_semana.csv (2020-2024)
BASE_SEMANAL = {
    "Pasto": {"IRA": 119.2, "EDA": 58.5, "DENGUE": 0.15, "RESP_CENIZA": 2.2},
    "Consacá": {"IRA": 3.2, "EDA": 1.4, "DENGUE": 0.55, "RESP_CENIZA": 0.35},
    "La Florida": {"IRA": 4.4, "EDA": 1.8, "DENGUE": 0.08, "RESP_CENIZA": 0.35},
    "Nariño": {"IRA": 5.2, "EDA": 2.4, "DENGUE": 0.06, "RESP_CENIZA": 0.4},
    "Sandoná": {"IRA": 7.5, "EDA": 3.6, "DENGUE": 0.8, "RESP_CENIZA": 0.5},
    "Yacuanquer": {"IRA": 3.0, "EDA": 1.2, "DENGUE": 0.03, "RESP_CENIZA": 0.3},
}

# Episodios SIMULADOS de caída de ceniza: (fecha, [municipios], intensidad 1-3)
# Los vientos dominantes llevan la ceniza del Galeras hacia el occidente (Consacá, Sandoná, La Florida).
CENIZA_SIMULADA = [
    ("2020-03-18", ["Consacá", "Sandoná"], 2),
    ("2020-11-02", ["La Florida", "Nariño"], 1),
    ("2021-06-14", ["Consacá", "Sandoná", "La Florida"], 3),
    ("2022-01-25", ["Yacuanquer", "Consacá"], 1),
    ("2022-09-07", ["Pasto", "Nariño"], 2),
    ("2023-04-19", ["Sandoná", "Consacá"], 2),
    ("2024-02-12", ["La Florida", "Sandoná"], 1),
    ("2024-10-28", ["Consacá", "Yacuanquer", "Pasto"], 2),
    ("2025-07-09", ["Sandoná", "La Florida"], 1),
    ("2026-03-11", ["Consacá", "Sandoná"], 2),
]

"""Master data of the seed. Names, descriptions and recommendations are Spanish: users read them.

Municipalities: the 6 of the previous system (Galeras area of influence), with La Florida's DIVIPOLA
code fixed (52381; the old dataset had 52299). Population and crater distance come from the previous
system; coordinates and altitude are those of the municipal seat (approx.). The ADMIN can fix them
from the panel.
"""

MUNICIPALITIES = [
    {"divipola_code": "52001", "name": "Pasto", "latitude": 1.2136, "longitude": -77.2811,
     "altitude_m": 2527, "population": 450000, "crater_distance_km": 9},
    {"divipola_code": "52207", "name": "Consacá", "latitude": 1.2078, "longitude": -77.4661,
     "altitude_m": 1730, "population": 14000, "crater_distance_km": 15},
    {"divipola_code": "52381", "name": "La Florida", "latitude": 1.2972, "longitude": -77.4064,
     "altitude_m": 2160, "population": 18000, "crater_distance_km": 22},
    {"divipola_code": "52480", "name": "Nariño", "latitude": 1.2892, "longitude": -77.3594,
     "altitude_m": 2240, "population": 22000, "crater_distance_km": 25},
    {"divipola_code": "52683", "name": "Sandoná", "latitude": 1.2847, "longitude": -77.4711,
     "altitude_m": 1848, "population": 30000, "crater_distance_km": 18},
    {"divipola_code": "52885", "name": "Yacuanquer", "latitude": 1.1158, "longitude": -77.4014,
     "altitude_m": 2620, "population": 13000, "crater_distance_km": 16},
]

DISEASES = [
    {
        "code": "IRA", "pharmacy_categories": "COLD_FLU,ANTIPYRETICS",
        "name": "Gripe / Infección Respiratoria Aguda",
        "description": "Infecciones de vías respiratorias (gripa, bronquitis, neumonía). Aumentan con el frío, "
                       "la humedad y las temporadas de lluvia.",
        "icd10_code": "J00-J22", "color": "#2a78d6",
        "search_terms": "gripa,tos,fiebre,dolor de garganta",
        "recommendations": "Lávate las manos con agua y jabón con frecuencia.\n"
                           "Usa tapabocas si tienes síntomas respiratorios y quédate en casa.\n"
                           "Abrígate en las noches frías y ventila los espacios cerrados.\n"
                           "Vacúnate contra la influenza (niños, mayores de 60 y gestantes).\n"
                           "Consulta de inmediato si hay dificultad para respirar o fiebre de más de 3 días.",
    },
    {
        "code": "EDA", "pharmacy_categories": "ORAL_REHYDRATION", "name": "Enfermedad Diarreica Aguda",
        "description": "Diarrea de origen infeccioso. Se asocia a lluvias fuertes (contaminación de fuentes "
                       "de agua) y a temporadas secas (escasez de agua).",
        "icd10_code": "A00-A09", "color": "#1baf7a",
        "search_terms": "diarrea",
        "recommendations": "Hierve o desinfecta el agua de consumo.\n"
                           "Lava frutas y verduras y cocina bien los alimentos.\n"
                           "Lávate las manos antes de comer y después de ir al baño.\n"
                           "Ante diarrea, usa sales de rehidratación oral y no te automediques.\n"
                           "Consulta si hay sangre en las heces, vómito persistente o signos de deshidratación.",
    },
    {
        "code": "DENGUE", "pharmacy_categories": "REPELLENTS,ANTIPYRETICS", "sivigila_codes": "210,220",
        "name": "Dengue",
        "description": "Transmitido por el mosquito Aedes aegypti, que casi no sobrevive por encima de "
                       "~1.800 m s. n. m.; por eso el riesgo se concentra en Consacá y Sandoná y en casos "
                       "importados en Pasto.",
        "icd10_code": "A90-A91", "color": "#e87ba4",
        "search_terms": "dengue,fiebre",
        "yellow_threshold_pct": 50, "orange_threshold_pct": 75, "red_threshold_pct": 90,
        "recommendations": "Elimina recipientes con agua estancada (llantas, floreros, tanques destapados).\n"
                           "Usa repelente y ropa de manga larga si viajas a zonas cálidas.\n"
                           "Instala toldillos y mallas en puertas y ventanas.\n"
                           "Ante fiebre alta con dolor de cuerpo o detrás de los ojos, consulta y no tomes "
                           "ibuprofeno ni aspirina.",
    },
    {
        "code": "RESP_CENIZA", "pharmacy_categories": "FACE_MASKS,INHALERS",
        "name": "Afección respiratoria por ceniza volcánica",
        "description": "Irritación de vías respiratorias, ojos y piel por caída de ceniza y gases (SO₂) del "
                       "Volcán Galeras. Afecta más a niños, adultos mayores y personas con asma o EPOC.",
        "icd10_code": "J68, J98.8", "color": "#4a3aa7",
        "search_terms": "ceniza volcán,tos",
        "recommendations": "Usa tapabocas N95 durante la caída de ceniza.\n"
                           "Cierra puertas y ventanas y evita actividades al aire libre.\n"
                           "Protege tanques y fuentes de agua de la ceniza.\n"
                           "Si tienes asma o EPOC, ten a mano tu inhalador y sigue tu plan de manejo.\n"
                           "Sigue los boletines del Servicio Geológico Colombiano y de la Gestión del Riesgo.",
    },
]

# Fictitious pharmacies (they are not real businesses)
PHARMACIES = [
    ("Droguería Demo Centro", "Pasto"), ("Droguería Demo Norte", "Pasto"),
    ("Droguería Demo Consacá", "Consacá"), ("Droguería Demo La Florida", "La Florida"),
    ("Droguería Demo Nariño", "Nariño"), ("Droguería Demo Sandoná", "Sandoná"),
    ("Droguería Demo Yacuanquer", "Yacuanquer"),
]

# Last REAL verified bulletin (SGC); the rest of the history is simulated
REAL_BULLETIN = {
    "start_date": "2026-08-25", "end_date": "2026-08-31", "activity_level": "YELLOW",
    "description": "Alerta Amarilla: volcán activo con cambios en el comportamiento del nivel base de los "
                   "parámetros monitoreados. Pequeñas emisiones de gases blancos de baja altura; sin reporte "
                   "de caída de ceniza.",
    "bulletin_url": "https://www2.sgc.gov.co/Noticias/boletinesDocumentos/"
                   "Boletin_semanal_de_actividad_del_volcan_galeras_del_25_al_31_de_agosto_de_2026.pdf",
}

# Calibration of the mean weekly cases (IRA/EDA) taken from
# BI_Health_Nari-o/data/final/dataset_final_municipio_semana.csv (2020-2024)
WEEKLY_BASELINE = {
    "Pasto": {"IRA": 119.2, "EDA": 58.5, "DENGUE": 0.15, "RESP_CENIZA": 2.2},
    "Consacá": {"IRA": 3.2, "EDA": 1.4, "DENGUE": 0.55, "RESP_CENIZA": 0.35},
    "La Florida": {"IRA": 4.4, "EDA": 1.8, "DENGUE": 0.08, "RESP_CENIZA": 0.35},
    "Nariño": {"IRA": 5.2, "EDA": 2.4, "DENGUE": 0.06, "RESP_CENIZA": 0.4},
    "Sandoná": {"IRA": 7.5, "EDA": 3.6, "DENGUE": 0.8, "RESP_CENIZA": 0.5},
    "Yacuanquer": {"IRA": 3.0, "EDA": 1.2, "DENGUE": 0.03, "RESP_CENIZA": 0.3},
}

# SIMULATED ash-fall episodes: (date, [municipalities], intensity 1-3)
# Prevailing winds carry Galeras ash westwards (Consacá, Sandoná, La Florida).
SIMULATED_ASH_FALLS = [
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

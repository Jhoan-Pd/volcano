/**
 * Fichas informativas de las enfermedades vigiladas. Es contenido editorial que no depende de
 * los datos semanales: por eso sus páginas son SSG (se generan una vez en el build).
 * Información general de salud pública; no reemplaza la consulta médica.
 */
export interface Ficha {
  codigo: string;
  nombre: string;
  resumen: string;
  sintomas: string[];
  transmision: string;
  grupos: string[];
  prevencion: string[];
  consultar: string[];
  /** Qué señales del predictor anticipan esta enfermedad. */
  senales: { grupo: string; detalle: string }[];
  contexto: string;
}

export const FICHAS: Record<string, Ficha> = {
  IRA: {
    codigo: "IRA",
    nombre: "Gripe e infección respiratoria aguda",
    resumen: "Infecciones de la nariz, la garganta, los bronquios o los pulmones causadas sobre todo por virus (influenza, virus "
      + "sincitial respiratorio, rinovirus, SARS-CoV-2). Son la causa más frecuente de consulta en temporada de lluvias.",
    sintomas: ["Tos y dolor de garganta", "Fiebre o escalofríos", "Congestión o secreción nasal", "Dolor de cabeza y cuerpo",
      "Dificultad para respirar en los casos graves"],
    transmision: "De persona a persona por gotas y aerosoles al toser, estornudar o hablar, y por manos o superficies contaminadas.",
    grupos: ["Menores de 5 años", "Mayores de 60 años", "Personas con asma, EPOC, diabetes o enfermedades del corazón", "Gestantes"],
    prevencion: ["Lavarse las manos con agua y jabón con frecuencia", "Cubrirse al toser o estornudar con el antebrazo",
      "Usar tapabocas si hay síntomas y evitar aglomeraciones", "Ventilar los espacios cerrados",
      "Vacunarse contra la influenza (especialmente niños, mayores y gestantes)"],
    consultar: ["Respiración rápida o con hundimiento de costillas", "Fiebre de más de 3 días", "Labios morados o somnolencia",
      "En niños: no quiere comer ni beber"],
    senales: [
      { grupo: "Clima", detalle: "Lluvia acumulada y humedad de las últimas semanas: con frío y lluvia la gente se reúne en espacios cerrados." },
      { grupo: "Búsquedas en internet", detalle: "Aumento de búsquedas de «gripa», «tos» o «fiebre» en Nariño frente a su nivel habitual." },
      { grupo: "Ventas en farmacias", detalle: "Más antigripales y antipiréticos vendidos que el promedio de las 52 semanas anteriores." },
      { grupo: "Estacionalidad", detalle: "Las mismas semanas del año anterior (picos con las temporadas de lluvia)." },
    ],
    contexto: "En Pasto (2 527 m s. n. m.) las temperaturas bajas y las dos temporadas de lluvia del año concentran los picos de IRA.",
  },
  EDA: {
    codigo: "EDA",
    nombre: "Enfermedad diarreica aguda",
    resumen: "Tres o más deposiciones líquidas en 24 horas, casi siempre por virus (rotavirus, norovirus), bacterias o parásitos "
      + "presentes en agua o alimentos contaminados. El mayor riesgo es la deshidratación.",
    sintomas: ["Deposiciones líquidas frecuentes", "Dolor o cólico abdominal", "Náuseas o vómito", "Fiebre en algunos casos",
      "Signos de deshidratación: boca seca, poca orina, ojos hundidos"],
    transmision: "Por agua o alimentos contaminados y de persona a persona cuando no hay buen lavado de manos.",
    grupos: ["Menores de 5 años", "Adultos mayores", "Hogares sin agua potable o saneamiento adecuado"],
    prevencion: ["Hervir o tratar el agua de consumo", "Lavarse las manos antes de comer y después de ir al baño",
      "Lavar y cocinar bien los alimentos", "Mantener la lactancia materna", "Tener sales de rehidratación oral en casa"],
    consultar: ["Sangre en las heces", "No puede beber o vomita todo", "Signos de deshidratación", "Diarrea por más de 3 días"],
    senales: [
      { grupo: "Clima", detalle: "Lluvias fuertes recientes: arrastran contaminantes a las fuentes de agua." },
      { grupo: "Ventas en farmacias", detalle: "Aumento en la venta de sales de rehidratación oral." },
      { grupo: "Búsquedas en internet", detalle: "Búsquedas de «diarrea» o «vómito» por encima de lo habitual." },
      { grupo: "Casos recientes", detalle: "Tendencia de las últimas 4 a 8 semanas en el municipio." },
    ],
    contexto: "En la zona rural de los municipios del Galeras parte del agua viene de acueductos veredales: las lluvias intensas elevan el riesgo.",
  },
  DENGUE: {
    codigo: "DENGUE",
    nombre: "Dengue",
    resumen: "Enfermedad viral transmitida por la picadura del mosquito Aedes aegypti. Se presenta en municipios cálidos por "
      + "debajo de unos 1 800 m s. n. m.; en Pasto, por la altura, los casos suelen ser importados.",
    sintomas: ["Fiebre alta de inicio súbito", "Dolor detrás de los ojos", "Dolor muscular y de articulaciones",
      "Erupción en la piel", "Signos de alarma: dolor abdominal intenso, vómito persistente, sangrado"],
    transmision: "Picadura del mosquito Aedes aegypti, que se cría en agua limpia estancada (tanques, llantas, floreros).",
    grupos: ["Personas que viven o viajan a zonas cálidas", "Niños y adultos mayores", "Quien ya tuvo dengue (más riesgo de dengue grave)"],
    prevencion: ["Lavar y tapar tanques y recipientes con agua cada semana", "Eliminar llantas, botellas y objetos que acumulen agua",
      "Usar repelente y ropa de manga larga", "Instalar toldillos y angeos"],
    consultar: ["Cualquier fiebre en zona de dengue: no automedicarse con ibuprofeno ni aspirina",
      "Dolor abdominal fuerte, vómito persistente o sangrado de encías", "Somnolencia o irritabilidad"],
    senales: [
      { grupo: "Clima", detalle: "Temperatura y lluvia de 4 a 6 semanas atrás: es el tiempo que tarda el ciclo del mosquito y del virus." },
      { grupo: "Municipio", detalle: "La altitud: en Consacá (≈1 730 m) el riesgo es mucho mayor que en Pasto." },
      { grupo: "Ventas en farmacias", detalle: "Repelentes y antipiréticos por encima de lo habitual." },
    ],
    contexto: "El calentamiento hace que el mosquito suba cada vez más en la cordillera: vigilar municipios de altura media es clave.",
  },
  RESP_CENIZA: {
    codigo: "RESP_CENIZA",
    nombre: "Afecciones respiratorias por ceniza volcánica",
    resumen: "Irritación de las vías respiratorias, los ojos y la piel por la ceniza y los gases (SO₂) que emite el Volcán Galeras. "
      + "Empeora el asma y la EPOC y puede desencadenar bronquitis.",
    sintomas: ["Tos seca e irritación de garganta", "Silbido en el pecho o sensación de ahogo", "Ojos rojos y ardor",
      "Secreción nasal", "Crisis de asma en personas asmáticas"],
    transmision: "No es contagiosa: se produce al respirar partículas finas de ceniza o gases volcánicos.",
    grupos: ["Personas con asma, EPOC o enfermedades del corazón", "Niños y adultos mayores",
      "Habitantes de municipios a favor del viento del cráter", "Trabajadores al aire libre"],
    prevencion: ["Usar tapabocas (idealmente N95) durante caídas de ceniza", "Cerrar puertas y ventanas",
      "Limpiar la ceniza humedeciéndola, sin barrer en seco", "Proteger los tanques de agua",
      "Seguir los boletines del Servicio Geológico Colombiano"],
    consultar: ["Dificultad para respirar que no mejora", "Crisis de asma que no cede con el inhalador", "Dolor en el pecho"],
    senales: [
      { grupo: "Actividad volcánica", detalle: "Emisión de SO₂ reportada en el boletín y caída de ceniza en el municipio en las últimas semanas." },
      { grupo: "Ventas en farmacias", detalle: "Más tapabocas e inhaladores vendidos que de costumbre." },
      { grupo: "Clima", detalle: "La lluvia «lava» la ceniza del aire; los días secos la mantienen suspendida." },
    ],
    contexto: "El Galeras es uno de los volcanes más activos de Colombia; Pasto está a unos 9 km del cráter.",
  },
};

export const CODIGOS = Object.keys(FICHAS);

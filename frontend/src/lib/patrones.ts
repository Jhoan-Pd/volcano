/**
 * Los cuatro patrones de rendering y dónde se usa cada uno en el predictor.
 * Lo leen el panel que aparece en cada página (RenderPanel) y la página /patrones.
 */
export type Patron = "SSG" | "ISR" | "SSR" | "CSR";

export interface InfoPatron {
  sigla: Patron;
  nombre: string;
  donde: string;
  cuando: string;
  seo: string;
  frescura: string;
  costo: string;
  paginas: { ruta: string; nombre: string }[];
  porQue: string;
  pista: string;
}

export const PATRONES: Record<Patron, InfoPatron> = {
  SSG: {
    sigla: "SSG",
    nombre: "Static Site Generation",
    donde: "En el build de Vercel, una sola vez",
    cuando: "Al ejecutar next build",
    seo: "Excelente: el HTML trae todo el contenido",
    frescura: "Congelada hasta el próximo despliegue",
    costo: "Casi cero: un archivo servido desde la CDN",
    paginas: [
      { ruta: "/enfermedades", nombre: "Fichas de enfermedades" },
      { ruta: "/metodologia", nombre: "Metodología" },
      { ruta: "/patrones", nombre: "Comparativa de patrones" },
    ],
    porQue: "Las fichas de cada enfermedad (síntomas, transmisión, prevención) no cambian con los datos semanales. "
      + "Generarlas en el build las hace instantáneas, indexables por buscadores y no gastan la API.",
    pista: "Recarga cuantas veces quieras: la hora no cambia hasta el próximo despliegue.",
  },
  ISR: {
    sigla: "ISR",
    nombre: "Incremental Static Regeneration",
    donde: "En el servidor, y luego se cachea en la CDN",
    cuando: "En el build y después como máximo cada hora, o al instante cuando el cron avisa",
    seo: "Excelente: el HTML trae todo el contenido",
    frescura: "Casi fresca: se regenera al llegar datos nuevos",
    costo: "Bajo: una regeneración por actualización, no por visita",
    paginas: [
      { ruta: "/", nombre: "Inicio" },
      { ruta: "/municipio/[id]", nombre: "Tablero de cada municipio" },
    ],
    porQue: "El riesgo cambia una vez al día (cron de las 6 a. m.) o cuando se reentrena el modelo, pero lo consulta mucha gente. "
      + "ISR sirve el tablero como página estática y el backend pide regenerarlo (revalidación bajo demanda) justo cuando hay datos nuevos.",
    pista: "Recarga varias veces: la hora solo cambia cuando hay datos nuevos o vence la hora de ISR.",
  },
  SSR: {
    sigla: "SSR",
    nombre: "Server-Side Rendering",
    donde: "En el servidor, en cada petición",
    cuando: "Cada vez que alguien abre la página o cambia un filtro",
    seo: "Excelente: el HTML trae los resultados",
    frescura: "Totalmente fresca: refleja la base de datos en ese instante",
    costo: "Alto: el servidor trabaja y consulta la API en cada visita",
    paginas: [
      { ruta: "/alertas", nombre: "Búsqueda de alertas" },
      { ruta: "/reportes", nombre: "Reportes" },
    ],
    porQue: "Los resultados dependen de lo que escribe el usuario (?q=, municipio, nivel…). Hay demasiadas combinaciones para "
      + "precalcularlas y cada URL se puede compartir con sus resultados ya renderizados.",
    pista: "Cada recarga o cambio de filtro genera un HTML nuevo: la hora cambia siempre.",
  },
  CSR: {
    sigla: "CSR",
    nombre: "Client-Side Rendering",
    donde: "En el navegador (JavaScript)",
    cuando: "Después de cargar la página: fetch, SSE o WebSocket hacia la API",
    seo: "Pobre: el HTML inicial llega sin datos (no importa en paneles privados)",
    frescura: "En tiempo real (streams del motor gRPC)",
    costo: "Bajo en el servidor; el trabajo lo hace el dispositivo",
    paginas: [
      { ruta: "/mapa", nombre: "Mapa de riesgo en vivo" },
      { ruta: "/simulador", nombre: "Simulador ¿qué pasa si…?" },
      { ruta: "/admin", nombre: "Administración" },
      { ruta: "/farmacia", nombre: "Panel de farmacia" },
    ],
    porQue: "Son páginas muy interactivas o privadas: el mapa de Leaflet necesita el navegador, el simulador conversa con el motor "
      + "por WebSocket y los paneles dependen del token del usuario. No necesitan SEO.",
    pista: "Los datos se piden desde tu navegador y llegan en vivo por SSE o WebSocket.",
  },
};

export const ORDEN: Patron[] = ["SSG", "ISR", "SSR", "CSR"];

/** Segundos de la ventana de ISR de los tableros (si el cron no avisa antes). */
export const REVALIDAR_TABLEROS = 3600;

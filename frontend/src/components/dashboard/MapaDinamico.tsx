"use client";

import dynamic from "next/dynamic";
import { Spinner } from "../ui";

/**
 * Leaflet necesita `window` y pesa ~150 kB: se descarga aparte y SOLO en el navegador.
 * `ssr: false` es la forma de Next.js de decir «este componente es 100 % CSR».
 */
const MapaRiesgo = dynamic(() => import("./MapaRiesgo"), {
  ssr: false,
  loading: () => <Spinner texto="Cargando mapa…" />,
});

export default MapaRiesgo;

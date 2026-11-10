"use client";

import dynamic from "next/dynamic";
import { useCallback, useState } from "react";
import { Spinner } from "../ui";
import type { PropsMapa } from "./modoMapa";

/**
 * Los mapas necesitan `window` y pesan: se descargan aparte y SOLO en el navegador.
 * `ssr: false` es la forma de Next.js de decir «este componente es 100 % CSR».
 *
 * Mejora progresiva: si hay clave de Google Maps (NEXT_PUBLIC_GOOGLE_MAPS_API_KEY) se usa Google
 * Maps con relieve y satélite; sin clave, o si Google la rechaza, se usa Leaflet, que no necesita
 * clave. Así el mapa nunca queda en blanco durante una presentación.
 */
const cargando = () => <Spinner texto="Cargando mapa…" />;
const MapaLeaflet = dynamic(() => import("./MapaRiesgo"), { ssr: false, loading: cargando });
const MapaGoogle = dynamic(() => import("./MapaGoogle"), { ssr: false, loading: cargando });

const CLAVE_GOOGLE = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "";

export default function MapaDinamico(props: PropsMapa) {
  const [falloGoogle, setFalloGoogle] = useState(false);
  const alFallar = useCallback(() => setFalloGoogle(true), []);
  if (CLAVE_GOOGLE && !falloGoogle) return <MapaGoogle {...props} apiKey={CLAVE_GOOGLE} onFallo={alFallar} />;
  return <MapaLeaflet {...props} />;
}

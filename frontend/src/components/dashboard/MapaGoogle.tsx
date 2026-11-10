"use client";

import {
  APILoadingStatus, APIProvider, Circle, InfoWindow, Map as GoogleMap, Marker, useApiLoadingStatus, useMap,
} from "@vis.gl/react-google-maps";
import { useEffect, useMemo, useState } from "react";
import type { RiesgoMunicipio } from "../../api/tipos";
import { useTema } from "../../context/ThemeContext";
import { NIVELES, ORDEN_NIVELES, rangoNivel } from "../../lib/formato";
import { nivelDe, type PropsMapa } from "./modoMapa";

// Cráter del Volcán Galeras (Servicio Geológico Colombiano)
const GALERAS = { lat: 1.2208, lng: -77.3592 };
const RADIO_KM = 15;
const ESPERA_MAX_MS = 10_000;

// Colores fijos del semáforo (Google Maps no lee variables CSS)
const COLOR_NIVEL: Record<string, string> = { VERDE: "#0ca30c", AMARILLO: "#fab219", NARANJA: "#ec835a", ROJO: "#d03b3b" };

const ICONO_VOLCAN = `data:image/svg+xml;utf8,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="34" height="29" viewBox="0 0 28 24"><path d="M2 22 L11 6 L14 9 L17 5 L26 22 Z" fill="#b8692a" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/><circle cx="19" cy="3" r="1.6" fill="#a8a29e"/></svg>`)}`;

// Estilo nocturno (solo se aplica en tema oscuro); con mapId no se podrían usar estilos en el cliente
const ESTILO_OSCURO: google.maps.MapTypeStyle[] = [
  { elementType: "geometry", stylers: [{ color: "#1d1d1d" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#a0a0a0" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#121212" }] },
  { featureType: "road", elementType: "geometry", stylers: [{ color: "#2c2c2c" }] },
  { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#1a1a1a" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#0e1a26" }] },
  { featureType: "poi", stylers: [{ visibility: "off" }] },
  { featureType: "transit", stylers: [{ visibility: "off" }] },
];
const ESTILO_CLARO: google.maps.MapTypeStyle[] = [
  { featureType: "poi", stylers: [{ visibility: "off" }] },
  { featureType: "transit", stylers: [{ visibility: "off" }] },
];

/**
 * Mapa de riesgo sobre Google Maps: relieve por defecto (se ve el cono del Galeras y los valles
 * donde están los municipios), con cambio a mapa o satélite. Si la clave falla (restricción de
 * dominio, API sin habilitar o sin facturación) se avisa con `onFallo` y se usa el mapa Leaflet.
 */
export default function MapaGoogle({ apiKey, onFallo, ...props }: PropsMapa & { apiKey: string; onFallo: () => void }) {
  return (
    <APIProvider apiKey={apiKey} language="es" region="CO">
      <Contenido {...props} onFallo={onFallo} />
    </APIProvider>
  );
}

function Contenido({ filas, modo, codigo, enfermedades, seleccionado, onSeleccionar, onFallo }:
  PropsMapa & { onFallo: () => void }) {
  const estado = useApiLoadingStatus();
  const { tema } = useTema();
  const [abierto, setAbierto] = useState<number | null>(null);

  useEffect(() => {
    if (estado === APILoadingStatus.FAILED || estado === APILoadingStatus.AUTH_FAILURE) onFallo();
  }, [estado, onFallo]);

  // Si Google no termina de cargar a tiempo (red lenta o bloqueada) se pasa a Leaflet
  useEffect(() => {
    if (estado === APILoadingStatus.LOADED) return;
    const id = setTimeout(onFallo, ESPERA_MAX_MS);
    return () => clearTimeout(id);
  }, [estado, onFallo]);

  // Los municipios con más riesgo se dibujan encima
  const ordenadas = useMemo(() => [...filas].sort((a, b) =>
    rangoNivel(nivelDe(a, modo, codigo)) - rangoNivel(nivelDe(b, modo, codigo))), [filas, modo, codigo]);
  const filaAbierta = filas.find((f) => f.municipio_id === abierto);

  // `google.maps` (Size, Point, SymbolPath) solo existe cuando terminó de cargar el script
  if (estado !== APILoadingStatus.LOADED) {
    return <div className="flex h-80 items-center justify-center rounded-lg border border-line text-sm text-muted sm:h-[26rem]">Cargando Google Maps…</div>;
  }

  return (
    <div className="relative isolate h-80 overflow-hidden rounded-lg border border-line sm:h-[26rem]">
      <GoogleMap className="h-full w-full" defaultCenter={GALERAS} defaultZoom={10} mapTypeId="terrain"
        styles={tema === "oscuro" ? ESTILO_OSCURO : ESTILO_CLARO} gestureHandling="cooperative"
        mapTypeControl mapTypeControlOptions={{ mapTypeIds: ["roadmap", "terrain", "hybrid"] }}
        streetViewControl={false} fullscreenControl clickableIcons={false} backgroundColor="var(--surface-2)">
        <Encuadre filas={filas} />
        <Circle center={GALERAS} radius={RADIO_KM * 1000} clickable={false}
          strokeColor="#b8692a" strokeOpacity={0.8} strokeWeight={1.5} fillColor="#b8692a" fillOpacity={0.06} />
        <Marker position={GALERAS} title={`Volcán Galeras · radio de referencia de ${RADIO_KM} km`} zIndex={1}
          icon={{ url: ICONO_VOLCAN, scaledSize: new google.maps.Size(34, 29), anchor: new google.maps.Point(17, 27) }} />
        {ordenadas.map((f, i) => {
          const n = nivelDe(f, modo, codigo);
          const activo = f.municipio_id === seleccionado;
          return (
            <Marker key={f.municipio_id} position={{ lat: f.latitud, lng: f.longitud }} zIndex={10 + i}
              title={`${f.municipio}: riesgo ${NIVELES[n].etiqueta.toLowerCase()}`}
              onClick={() => { setAbierto(f.municipio_id); onSeleccionar(f.municipio_id); }}
              icon={{ path: google.maps.SymbolPath.CIRCLE, scale: activo ? 13 : 10, fillColor: COLOR_NIVEL[n],
                      fillOpacity: 0.95, strokeColor: "#ffffff", strokeWeight: activo ? 3 : 2,
                      labelOrigin: new google.maps.Point(0, -2.4) }}
              label={{ text: f.municipio, fontSize: "12px", fontWeight: "600",
                       color: tema === "oscuro" ? "#ffffff" : "#1a1a1a", className: "mapa-google-etiqueta" }} />
          );
        })}
        {filaAbierta && (
          <InfoWindow position={{ lat: filaAbierta.latitud, lng: filaAbierta.longitud }}
            pixelOffset={[0, -14]} onCloseClick={() => setAbierto(null)} headerContent={
              <p className="text-sm font-semibold text-neutral-900">{filaAbierta.municipio}</p>}>
            <table className="text-xs text-neutral-800">
              <thead><tr><th className="pr-3 text-left font-medium">Enfermedad</th><th className="pr-3 text-left font-medium">Actual</th><th className="text-left font-medium">4 semanas</th></tr></thead>
              <tbody>
                {enfermedades.map((e) => (
                  <tr key={e.codigo}>
                    <td className="pr-3">{e.nombre}</td>
                    <td className="pr-3">{NIVELES[filaAbierta.detalle[e.codigo] ?? "VERDE"].etiqueta}</td>
                    <td>{filaAbierta.detalle_predicho[e.codigo] ? NIVELES[filaAbierta.detalle_predicho[e.codigo]].etiqueta : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </InfoWindow>
        )}
      </GoogleMap>
      <ul className="pointer-events-none absolute bottom-6 left-2 z-[1] flex flex-wrap gap-x-3 gap-y-1 rounded-lg border border-line bg-surface/90 px-2.5 py-1.5 text-[11px] text-ink-2 backdrop-blur"
        aria-label="Leyenda del mapa">
        {ORDEN_NIVELES.map((n) => (
          <li key={n} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: NIVELES[n].color }} />{NIVELES[n].etiqueta}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Ajusta la vista para que entren todos los municipios y el volcán (una sola vez por conjunto). */
function Encuadre({ filas }: { filas: RiesgoMunicipio[] }) {
  const map = useMap();
  const clave = filas.map((f) => f.municipio_id).join(",");
  useEffect(() => {
    if (!map || !filas.length) return;
    const limites = new google.maps.LatLngBounds(GALERAS);
    filas.forEach((f) => limites.extend({ lat: f.latitud, lng: f.longitud }));
    map.fitBounds(limites, 48);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo cuando cambia el conjunto de municipios
  }, [map, clave]);
  return null;
}

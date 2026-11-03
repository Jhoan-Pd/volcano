import { Spinner } from "@/components/ui";

/** Se muestra mientras una página de servidor (SSR o una regeneración ISR) espera a la API. */
export default function Cargando() {
  return <Spinner texto="Consultando la API… (si el backend de Render estaba dormido puede tardar ~1 minuto)" />;
}

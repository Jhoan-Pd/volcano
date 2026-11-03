// FARMACIA — CSR: panel privado del rol FARMACIA (token en el navegador). La carga masiva de
// reportes revisa el CSV en un Web Worker y lo envía al motor por client streaming de gRPC.
import type { Metadata } from "next";
import { PanelCSR } from "@/components/render/PanelCSR";
import RutaProtegida from "@/components/RutaProtegida";
import FarmaciaPage from "@/vistas/FarmaciaPage";

export const metadata: Metadata = { title: "Panel de farmacia", robots: { index: false } };

export default function PaginaFarmacia() {
  return (
    <div className="space-y-5">
      <PanelCSR porQue="Cada farmacia ve solo sus reportes: los datos dependen del usuario que inició sesión y se piden desde el navegador." />
      <RutaProtegida roles={["FARMACIA", "ADMIN"]}><FarmaciaPage /></RutaProtegida>
    </div>
  );
}

// ============================================================================
// ADMINISTRACIÓN — CSR (Client-Side Rendering)
// ----------------------------------------------------------------------------
// El servidor solo entrega el cascarón: el token del administrador vive en localStorage, así
// que los datos solo se pueden pedir desde el navegador. Aquí se entrena el modelo con el
// stream gRPC (SSE) y se revisan los CSV con un Web Worker antes de subirlos.
// ============================================================================
import type { Metadata } from "next";
import { PanelCSR } from "@/components/render/PanelCSR";
import RutaProtegida from "@/components/RutaProtegida";
import AdminPage from "@/vistas/AdminPage";

export const metadata: Metadata = { title: "Administración", robots: { index: false } };

export default function PaginaAdmin() {
  return (
    <div className="space-y-5">
      <PanelCSR porQue="Es un panel privado: depende del token del administrador (que el servidor no ve) y es muy interactivo. No necesita SEO." />
      <RutaProtegida roles={["ADMIN"]}><AdminPage /></RutaProtegida>
    </div>
  );
}

/**
 * Layout raíz (componente de SERVIDOR). Se renderiza una vez y envuelve todas las páginas.
 * Las partes interactivas (cabecera con sesión, banner de alertas en vivo) son componentes de
 * cliente que se hidratan dentro de este HTML.
 */
import type { Metadata, Viewport } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
// Tipografías libres (OFL) servidas desde el propio sitio, sin depender de Google Fonts
import "@fontsource-variable/bricolage-grotesque/standard.css"; // títulos (ejes de peso y ancho)
import "@fontsource-variable/hanken-grotesk"; // texto
import "@fontsource-variable/geist"; // cifras grandes
import "@/index.css";
import AvisoServidor from "@/components/AvisoServidor";
import BannerAlertas from "@/components/BannerAlertas";
import Cabecera from "@/components/Cabecera";
import Proveedores from "./proveedores";

export const metadata: Metadata = {
  title: { default: "Predictor de Brotes · Nariño", template: "%s · Predictor de Brotes" },
  description: "Predictor de brotes de enfermedades para Pasto y la zona del Volcán Galeras (Nariño) con datos públicos y búsquedas locales.",
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

// Aplica el tema antes de pintar para evitar el "parpadeo" claro/oscuro
const SCRIPT_TEMA = `try{var t=localStorage.getItem("tema");var o=t?t==="oscuro":matchMedia("(prefers-color-scheme: dark)").matches;document.documentElement.classList.toggle("dark",o)}catch(e){}`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: SCRIPT_TEMA }} />
      </head>
      <body>
        <Proveedores>
          <div className="flex min-h-screen flex-col">
            <Cabecera />
            <AvisoServidor />
            <BannerAlertas />
            <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">{children}</main>
            <footer className="border-t border-line">
              <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-5 text-xs text-muted sm:px-6 md:flex-row md:justify-between">
                <p>
                  Proyecto académico · Programación Orientada a la Web · Nariño, Colombia ·{" "}
                  <Link href="/metodologia" className="subrayar text-ink-2">Metodología</Link> ·{" "}
                  <Link href="/patrones" className="subrayar text-ink-2">Patrones de rendering</Link>
                </p>
                <p>Fuentes: Open-Meteo · Google Trends · Servicio Geológico Colombiano · INS/SIVIGILA (datos.gov.co) · farmacias participantes</p>
              </div>
            </footer>
          </div>
        </Proveedores>
      </body>
    </html>
  );
}

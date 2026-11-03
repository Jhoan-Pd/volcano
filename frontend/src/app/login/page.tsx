// LOGIN — CSR: el formulario y la sesión (token en localStorage) viven en el navegador.
import type { Metadata } from "next";
import { Suspense } from "react";
import { Spinner } from "@/components/ui";
import LoginPage from "@/vistas/LoginPage";

export const metadata: Metadata = { title: "Ingresar" };

export default function PaginaLogin() {
  // useSearchParams (?desde=) exige un límite de Suspense para que el resto se pueda prerenderizar
  return <Suspense fallback={<Spinner />}><LoginPage /></Suspense>;
}

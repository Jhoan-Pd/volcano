"use server";

import { revalidatePath } from "next/cache";

/**
 * Server Action: revalidación bajo demanda (on-demand ISR) desde el botón del panel.
 * Invalida la caché de una página ISR para que la próxima visita reciba una versión nueva,
 * sin esperar a que venza la ventana de `revalidate`.
 */
export async function revalidarAhora(ruta: string): Promise<{ ok: boolean; mensaje: string }> {
  if (ruta !== "/" && !/^\/municipio\/\d+$/.test(ruta)) {
    return { ok: false, mensaje: "Ruta no permitida para revalidación" };
  }
  revalidatePath(ruta);
  return { ok: true, mensaje: `Revalidada ${ruta}` };
}

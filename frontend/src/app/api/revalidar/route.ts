/**
 * Route Handler: revalidación bajo demanda que dispara el BACKEND (cron diario y cada
 * reentrenamiento del modelo). Protegido con un secreto compartido:
 *
 *   POST /api/revalidar   Authorization: Bearer <REVALIDAR_SECRET>
 *
 * Invalida la portada y TODOS los tableros /municipio/[id] (revalidatePath con el patrón
 * dinámico y tipo "page"). Vercel los regenera en la siguiente visita.
 */
import { revalidatePath } from "next/cache";
import { NextResponse, type NextRequest } from "next/server";

export async function POST(request: NextRequest) {
  const secreto = process.env.REVALIDAR_SECRET;
  const recibido = request.headers.get("authorization");
  if (!secreto || recibido !== `Bearer ${secreto}`) {
    return NextResponse.json({ error: { codigo: "NO_AUTENTICADO", mensaje: "Secreto inválido" } }, { status: 401 });
  }
  revalidatePath("/");
  revalidatePath("/municipio/[id]", "page");
  return NextResponse.json({ rutas: ["/", "/municipio/[id]"], revalidado_en: new Date().toISOString() });
}

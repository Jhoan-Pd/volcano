/**
 * Lector de Server-Sent Events sobre fetch.
 *
 * EventSource (el API nativo) solo hace GET y no deja enviar cabeceras: sirve para el stream
 * público de alertas, pero no para entrenar, que es un POST con el token del administrador.
 * Aquí se lee el cuerpo de la respuesta con un ReadableStream y se separan los eventos según el
 * formato text/event-stream («event:», «data:» y una línea en blanco al final de cada evento).
 */
export interface EventoSSE<T = unknown> {
  evento: string;
  datos: T;
}

export class ErrorSSE extends Error {
  constructor(public estado: number, mensaje: string, public codigo?: string) {
    super(mensaje);
  }
}

export async function* leerSSE<T>(url: string, init: RequestInit = {}): AsyncGenerator<EventoSSE<T>> {
  const r = await fetch(url, { ...init, headers: { Accept: "text/event-stream", ...init.headers } });
  if (!r.ok || !r.body) {
    // Antes de abrir el stream la API responde errores normales en JSON (409, 403, 503…)
    let mensaje = `Error ${r.status}`;
    let codigo: string | undefined;
    try {
      const cuerpo = await r.json();
      mensaje = cuerpo?.error?.mensaje ?? mensaje;
      codigo = cuerpo?.error?.codigo;
    } catch { /* sin cuerpo JSON */ }
    throw new ErrorSSE(r.status, mensaje, codigo);
  }
  const lector = r.body.pipeThrough(new TextDecoderStream()).getReader();
  let pendiente = "";
  try {
    while (true) {
      const { value, done } = await lector.read();
      if (done) break;
      pendiente += value;
      let corte: number;
      while ((corte = pendiente.search(/\r?\n\r?\n/)) >= 0) {
        const bloque = pendiente.slice(0, corte);
        pendiente = pendiente.slice(corte).replace(/^\r?\n\r?\n/, "");
        let evento = "message";
        const datos: string[] = [];
        for (const linea of bloque.split(/\r?\n/)) {
          if (linea.startsWith(":")) continue; // comentario (keepalive)
          if (linea.startsWith("event:")) evento = linea.slice(6).trim();
          else if (linea.startsWith("data:")) datos.push(linea.slice(5).trimStart());
        }
        if (datos.length) yield { evento, datos: JSON.parse(datos.join("\n")) as T };
      }
    }
  } finally {
    lector.cancel().catch(() => undefined);
  }
}

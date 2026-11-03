// Antes de `next build`: despierta el backend de Render (plan gratis, se duerme tras 15 min).
// En el build se generan las páginas SSG e ISR pidiendo datos a la API; si estuviera dormida,
// la portada saldría sin datos. Nunca hace fallar el build: si la API no responde, las páginas
// usan su versión de respaldo y se regeneran solas en cuanto la API vuelve.
const base = (process.env.NEXT_PUBLIC_API_URL ?? process.env.VITE_API_URL ?? "").replace(/\/$/, "");
if (!base || /localhost|127\.0\.0\.1/.test(base) && !process.env.DESPERTAR_LOCAL) {
  console.log("[despertar-api] Sin API remota configurada: se omite.");
  process.exit(0);
}
const limite = Date.now() + 150_000;
for (let intento = 1; Date.now() < limite; intento++) {
  try {
    const r = await fetch(`${base}/health`, { signal: AbortSignal.timeout(20_000) });
    if (r.ok) {
      console.log(`[despertar-api] API lista (${base}) en el intento ${intento}.`);
      process.exit(0);
    }
  } catch { /* sigue intentando */ }
  console.log(`[despertar-api] Intento ${intento}: la API aún no responde…`);
  await new Promise((r) => setTimeout(r, 10_000));
}
console.log("[despertar-api] La API no respondió; el build continúa con páginas de respaldo.");

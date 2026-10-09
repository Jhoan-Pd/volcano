"""Seed de la base de datos (idempotente).

Uso (desde backend/):
    python -m app.seed            # carga lo que falte (seguro de repetir; Render lo ejecuta en cada arranque)
    python -m app.seed --reset    # BORRA todos los datos y vuelve a cargar
    python -m app.seed --sin-red  # no intenta Open-Meteo (clima 100 % simulado, útil sin internet)
    python -m app.seed --entrenar # además entrena los modelos y genera predicciones (≈1 min en local)
"""
import argparse
import csv
import logging
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from sqlalchemy import delete, func, insert, select

from app.core.config import settings
from app.core.epi import inicio_semana, iterar_semanas, semana_de, ultima_semana_completa
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.fuentes import FuenteDatosError, OpenMeteoFuente
from app.models import (
    Alerta, CasoOficial, Enfermedad, EventoVolcanico, Farmacia, ModeloEntrenado, Municipio, Prediccion,
    RegistroClima, ReporteFarmacia, Rol, TendenciaBusqueda, Usuario,
)
from app.models.enums import RolNombre
from app.seed import catalogo
from app.seed.generador import (
    clima_semanal, generar_casos, generar_reportes_farmacia, generar_tendencias, simular_clima,
)

log = logging.getLogger("seed")
DATA = Path(__file__).parent / "data"
SEMILLA = 42


def _hay(db, modelo) -> bool:
    return (db.scalar(select(func.count()).select_from(modelo)) or 0) > 0


def reset(db) -> None:
    for modelo in (Alerta, Prediccion, ModeloEntrenado, ReporteFarmacia, Farmacia, CasoOficial,
                   TendenciaBusqueda, RegistroClima, EventoVolcanico, Usuario, Enfermedad, Municipio, Rol):
        db.execute(delete(modelo))
    db.commit()
    log.info("Datos eliminados")


def seed_roles_usuarios(db) -> None:
    if not _hay(db, Rol):
        db.add_all([
            Rol(nombre=RolNombre.ADMIN, descripcion="Administra catálogos, usuarios, eventos y el modelo"),
            Rol(nombre=RolNombre.FARMACIA, descripcion="Reporta ventas semanales de su farmacia"),
            Rol(nombre=RolNombre.CIUDADANO, descripcion="Consulta el dashboard y recibe alertas"),
        ])
        db.commit()
    roles = {r.nombre: r.id for r in db.scalars(select(Rol))}
    pasto = db.scalar(select(Municipio.id).where(Municipio.codigo_divipola == "52001"))
    usuarios = [
        (settings.ADMIN_NOMBRE, settings.ADMIN_EMAIL, settings.ADMIN_PASSWORD, RolNombre.ADMIN),
        ("Farmacia Demo Centro", "farmacia@demo.co", settings.DEMO_PASSWORD, RolNombre.FARMACIA),
        ("Ciudadano Demo", "ciudadano@demo.co", settings.DEMO_PASSWORD, RolNombre.CIUDADANO),
    ]
    for nombre, email, pwd, rol in usuarios:
        if db.scalar(select(Usuario).where(Usuario.email == email.lower())) is None:
            db.add(Usuario(nombre=nombre, email=email.lower(), password_hash=hash_password(pwd),
                           rol_id=roles[rol], municipio_id=pasto))
    db.commit()


def seed_catalogos(db) -> None:
    if not _hay(db, Municipio):
        db.add_all([Municipio(departamento="Nariño", **m) for m in catalogo.MUNICIPIOS])
    if not _hay(db, Enfermedad):
        db.add_all([Enfermedad(**e) for e in catalogo.ENFERMEDADES])
    db.commit()


def seed_farmacias(db) -> None:
    if _hay(db, Farmacia):
        return
    muni = {m.nombre: m for m in db.scalars(select(Municipio))}
    usuario_farmacia = db.scalar(select(Usuario).where(Usuario.email == "farmacia@demo.co"))
    for i, (nombre, mun) in enumerate(catalogo.FARMACIAS):
        m = muni[mun]
        db.add(Farmacia(
            nombre=nombre, nit=f"90{i:07d}-{i % 10}", direccion=f"Calle {10 + i} # {5 + i}-{20 + i}, {mun}",
            telefono=f"602 7{i:02d} 0000", municipio_id=m.id,
            usuario_id=usuario_farmacia.id if i == 0 and usuario_farmacia else None,
            latitud=m.latitud + 0.002 * (i % 3), longitud=m.longitud - 0.002 * (i % 2),
        ))
    db.commit()


def seed_clima(db, usar_red: bool, devolver: bool = True) -> dict[int, list[dict]]:
    """Carga el clima si falta. Si `devolver`, retorna el clima diario por municipio (para generar casos)."""
    hoy = date.today()
    desde = date(settings.SEED_ANIO_INICIO, 1, 1) - timedelta(days=60)  # margen para los rezagos
    municipios = list(db.scalars(select(Municipio).order_by(Municipio.id)))
    if _hay(db, RegistroClima):
        log.info("Clima ya cargado; se reutiliza")
        if not devolver:
            return {}
        salida = {}
        for m in municipios:
            regs = db.scalars(select(RegistroClima).where(RegistroClima.municipio_id == m.id)).all()
            salida[m.id] = [{c: getattr(r, c) for c in ("fecha", "temp_media_c", "humedad_relativa_pct",
                                                        "precipitacion_mm", "es_pronostico")} for r in regs]
        return salida

    fuente = OpenMeteoFuente()
    salida = {}
    for m in municipios:
        filas: list[dict] = []
        if usar_red and settings.SEED_CLIMA_REAL:
            try:
                t0 = time.time()
                filas = fuente.obtener(latitud=m.latitud, longitud=m.longitud, modo="historico",
                                       desde=desde, hasta=hoy - timedelta(days=1))
                recientes = fuente.obtener(latitud=m.latitud, longitud=m.longitud, modo="pronostico", dias_pasados=10)
                por_fecha = {f["fecha"]: f for f in filas}
                por_fecha.update({f["fecha"]: f for f in recientes})
                filas = sorted(por_fecha.values(), key=lambda f: f["fecha"])
                log.info("Clima REAL Open-Meteo %s: %d días (%.1fs)", m.nombre, len(filas), time.time() - t0)
            except FuenteDatosError as exc:
                log.warning("Open-Meteo no disponible para %s (%s): se usa clima simulado", m.nombre, exc)
                filas = []
        if not filas:
            filas = simular_clima({"altitud_m": m.altitud_m}, desde, hoy + timedelta(days=15), hoy, SEMILLA + int(m.codigo_divipola))
        db.execute(insert(RegistroClima), [{**f, "municipio_id": m.id} for f in filas])
        db.commit()
        salida[m.id] = filas
    return salida


def _so2_historico() -> dict[tuple[int, int], float]:
    with open(DATA / "galeras_so2_semanal.csv", encoding="utf-8") as fh:
        return {(int(r["anio"]), int(r["semana_epi"])): float(r["so2_ton_dia"]) for r in csv.DictReader(fh)}


def seed_volcan(db) -> tuple[dict[tuple[int, int], float], dict[int, dict[tuple[int, int], int]]]:
    """Boletines semanales + caídas de ceniza. Devuelve SO2 semanal y ceniza por municipio para los casos."""
    rng = np.random.default_rng(SEMILLA)
    so2 = _so2_historico()
    fin = ultima_semana_completa()
    # Se extiende la serie 2025-2026 con valores del mismo rango (simulados)
    for a, s in iterar_semanas((2025, 1), fin):
        so2.setdefault((a, s), round(float(np.clip(rng.normal(380, 120), 90, 900)), 1))

    muni = {m.nombre: m.id for m in db.scalars(select(Municipio))}
    ceniza: dict[int, dict[tuple[int, int], int]] = {mid: {} for mid in muni.values()}
    for f, nombres, intensidad in catalogo.CENIZA_SIMULADA:
        k = semana_de(date.fromisoformat(f))
        for n in nombres:
            ceniza[muni[n]][k] = max(ceniza[muni[n]].get(k, 0), intensidad)

    if _hay(db, EventoVolcanico):
        return so2, ceniza

    real_ini = date.fromisoformat(catalogo.BOLETIN_REAL["fecha_inicio"])
    filas = []
    for (a, s), v in sorted(so2.items()):
        ini = inicio_semana(a, s)
        if ini >= real_ini - timedelta(days=3):
            break
        # El Galeras ha permanecido en Alerta Amarilla del SGC en este periodo; el SO2 es estimado
        filas.append({"tipo": "BOLETIN", "nivel_actividad": "AMARILLO", "fecha_inicio": ini,
                      "fecha_fin": ini + timedelta(days=6), "so2_ton_dia": v, "intensidad_ceniza": 0,
                      "descripcion": "Boletín semanal (SO₂ estimado, dato simulado para la semilla)",
                      "es_simulado": True})
    filas.append({"tipo": "BOLETIN", "nivel_actividad": catalogo.BOLETIN_REAL["nivel_actividad"],
                  "fecha_inicio": real_ini, "fecha_fin": date.fromisoformat(catalogo.BOLETIN_REAL["fecha_fin"]),
                  "descripcion": catalogo.BOLETIN_REAL["descripcion"], "url_boletin": catalogo.BOLETIN_REAL["url_boletin"],
                  "intensidad_ceniza": 0, "es_simulado": False})
    etiquetas = {1: "leve", 2: "moderada", 3: "fuerte"}
    for f, nombres, intensidad in catalogo.CENIZA_SIMULADA:
        for n in nombres:
            filas.append({"tipo": "CAIDA_CENIZA", "nivel_actividad": "AMARILLO", "fecha_inicio": date.fromisoformat(f),
                          "fecha_fin": date.fromisoformat(f) + timedelta(days=1), "municipio_id": muni[n],
                          "intensidad_ceniza": intensidad,
                          "descripcion": f"Caída de ceniza {etiquetas[intensidad]} (evento simulado para la semilla)",
                          "es_simulado": True})
    db.execute(insert(EventoVolcanico), filas)
    db.commit()
    return so2, ceniza


def seed_casos(db, clima: dict[int, list[dict]], so2, ceniza) -> None:
    if _hay(db, CasoOficial):
        return
    enf = {e.codigo: e.id for e in db.scalars(select(Enfermedad))}
    fin = ultima_semana_completa()
    total = 0
    for m in db.scalars(select(Municipio).order_by(Municipio.id)):
        base = catalogo.BASE_SEMANAL.get(m.nombre) or {k: 1.0 for k in enf}
        series = generar_casos(
            municipio=m.nombre, poblacion=m.poblacion, base=base, clima=clima_semanal(clima[m.id]), so2=so2,
            ceniza=ceniza.get(m.id, {}), desde=(settings.SEED_ANIO_INICIO, 1), hasta=fin, semilla=SEMILLA + int(m.codigo_divipola),
        )
        filas = [{"municipio_id": m.id, "enfermedad_id": enf[cod], "anio": a, "semana_epi": s, "casos": c,
                  "fuente": "SIVIGILA (simulado)", "es_simulado": True}
                 for cod, puntos in series.items() if cod in enf for a, s, c in puntos]
        db.execute(insert(CasoOficial), filas)
        db.commit()
        total += len(filas)
    log.info("Casos semanales generados: %d", total)


def _casos_por_municipio(db) -> dict[int, dict[str, dict[tuple[int, int], int]]]:
    enf = {e.id: e.codigo for e in db.scalars(select(Enfermedad))}
    salida: dict[int, dict[str, dict[tuple[int, int], int]]] = {}
    for mid, eid, a, s, c in db.execute(select(CasoOficial.municipio_id, CasoOficial.enfermedad_id, CasoOficial.anio,
                                               CasoOficial.semana_epi, CasoOficial.casos)):
        salida.setdefault(mid, {}).setdefault(enf[eid], {})[(a, s)] = c
    return salida


def _lista(texto: str | None) -> list[str]:
    return [t.strip() for t in (texto or "").split(",") if t.strip()]


def seed_tendencias(db) -> None:
    """Búsquedas simuladas (Google Trends CO-NAR) coherentes con los casos ya cargados."""
    if _hay(db, TendenciaBusqueda) or not _hay(db, CasoOficial):
        return
    por_mun = _casos_por_municipio(db)
    departamento: dict[str, dict[tuple[int, int], int]] = {}
    for series in por_mun.values():
        for cod, serie in series.items():
            destino = departamento.setdefault(cod, {})
            for k, v in serie.items():
                destino[k] = destino.get(k, 0) + v
    terminos = {e.codigo: [t.lower() for t in _lista(e.terminos_busqueda)] for e in db.scalars(select(Enfermedad))}
    filas = generar_tendencias(casos=departamento, terminos=terminos, desde=(settings.SEED_ANIO_INICIO, 1),
                               hasta=ultima_semana_completa(), semilla=SEMILLA + 7)
    db.execute(insert(TendenciaBusqueda), filas)
    db.commit()
    log.info("Búsquedas simuladas: %d semanas-término", len(filas))


def seed_reportes_farmacia(db) -> None:
    """Ventas semanales simuladas de las farmacias demo, coherentes con los casos de su municipio."""
    if _hay(db, ReporteFarmacia) or not _hay(db, CasoOficial):
        return
    altitudes = {m.id: m.altitud_m for m in db.scalars(select(Municipio))}
    farmacias = [{"id": f.id, "municipio_id": f.municipio_id, "altitud_m": altitudes.get(f.municipio_id)}
                 for f in db.scalars(select(Farmacia).order_by(Farmacia.id))]
    categorias = {e.codigo: _lista(e.categorias_farmacia) for e in db.scalars(select(Enfermedad))}
    filas = generar_reportes_farmacia(farmacias=farmacias, casos=_casos_por_municipio(db), categorias=categorias,
                                      desde=(settings.SEED_ANIO_INICIO, 1), hasta=ultima_semana_completa(),
                                      semilla=SEMILLA + 11)
    for i in range(0, len(filas), 5000):
        db.execute(insert(ReporteFarmacia), filas[i:i + 5000])
    db.commit()
    log.info("Reportes de farmacia simulados: %d filas", len(filas))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description="Carga datos iniciales")
    p.add_argument("--reset", action="store_true", help="borra todos los datos antes de cargar")
    p.add_argument("--sin-red", action="store_true", help="no consultar Open-Meteo")
    p.add_argument("--entrenar", action="store_true", help="entrenar modelos y generar predicciones")
    args = p.parse_args()

    t0 = time.time()
    with SessionLocal() as db:
        if args.reset:
            reset(db)
        seed_catalogos(db)
        seed_roles_usuarios(db)
        seed_farmacias(db)
        faltan_casos = not _hay(db, CasoOficial)
        clima = seed_clima(db, usar_red=not args.sin_red, devolver=faltan_casos)
        so2, ceniza = seed_volcan(db)
        if faltan_casos:
            seed_casos(db, clima, so2, ceniza)
        seed_tendencias(db)
        seed_reportes_farmacia(db)
        if args.entrenar:
            from app.services.prediccion_service import PrediccionService

            modelos, errores = PrediccionService(db).entrenar()
            log.info("Modelos entrenados: %d %s", len(modelos), errores or "")
    log.info("Seed completo en %.1fs", time.time() - t0)


if __name__ == "__main__":
    main()

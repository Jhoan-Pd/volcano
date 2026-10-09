"""Carga de CSV desde el panel de administración."""
from app.models import CasoOficial, EventoVolcanico


def _subir(client, headers, tipo, texto):
    return client.post(f"/api/v1/datos/importar/{tipo}", headers=headers,
                       files={"archivo": (f"{tipo}.csv", texto.encode("utf-8"), "text/csv")})


def test_importar_casos_inserta_y_luego_actualiza(client, admin_headers, db):
    csv = "cod_divipola,enfermedad,anio,semana_epi,casos\n52001,IRA,2019,10,77\n52001,IRA,2019,11,80\n"
    r = _subir(client, admin_headers, "casos", csv)
    assert r.status_code == 200, r.text
    assert r.json()["insertadas"] == 2 and r.json()["errores"] == []
    r = _subir(client, admin_headers, "casos", csv.replace(",77", ",99"))
    assert r.json()["actualizadas"] == 2 and r.json()["insertadas"] == 0
    c = db.query(CasoOficial).filter_by(anio=2019, semana_epi=10).one()
    assert c.casos == 99 and c.fuente == "CSV" and not c.es_simulado


def test_filas_invalidas_se_reportan_con_su_linea(client, admin_headers):
    csv = ("cod_divipola;enfermedad;anio;semana_epi;casos\n"  # separador ; (Excel en español)
           "52001;IRA;2019;12;5\n99999;IRA;2019;12;5\n52001;XYZ;2019;12;5\n52001;IRA;2019;60;5\n52001;IRA;2019;13;-1\n")
    r = _subir(client, admin_headers, "casos", csv)
    datos = r.json()
    assert datos["filas_leidas"] == 5 and datos["insertadas"] == 1
    assert [e["fila"] for e in datos["errores"]] == [3, 4, 5, 6]


def test_columnas_faltantes_y_tipo_invalido(client, admin_headers):
    r = _subir(client, admin_headers, "casos", "municipio,casos\nPasto,3\n")
    assert r.status_code == 422 and "Faltan columnas" in r.json()["error"]["mensaje"]
    assert _subir(client, admin_headers, "otro", "a\n1\n").status_code == 422


def test_importar_eventos_valida_ceniza(client, admin_headers, db):
    csv = ("tipo,nivel_actividad,fecha_inicio,cod_divipola,intensidad_ceniza,so2_ton_dia,descripcion\n"
           "CAIDA_CENIZA,AMARILLO,2019-03-01,52207,2,,prueba\nCAIDA_CENIZA,AMARILLO,2019-03-02,,0,,sin municipio\n")
    r = _subir(client, admin_headers, "eventos", csv)
    assert r.json()["insertadas"] == 1 and len(r.json()["errores"]) == 1
    assert db.query(EventoVolcanico).filter_by(descripcion="prueba").count() == 1


def test_importar_tendencias_y_clima(client, admin_headers):
    r = _subir(client, admin_headers, "tendencias", "termino,fecha_semana,indice\nfiebre,2019-01-06,40\ntos,2019-01-06,140\n")
    assert r.json()["insertadas"] == 1 and r.json()["errores"][0]["fila"] == 3
    r = _subir(client, admin_headers, "clima",
               "cod_divipola,fecha,temp_max_c,temp_min_c,temp_media_c,precipitacion_mm,humedad_relativa_pct\n"
               "52001,2019-01-01,19,8,13,2.5,85\n")
    assert r.json()["insertadas"] == 1


def test_importar_y_estado_solo_admin(client, ciudadano_headers, admin_headers):
    assert _subir(client, ciudadano_headers, "casos", "x\n").status_code == 403
    assert client.get("/api/v1/datos/estado", headers=ciudadano_headers).status_code == 403
    estado = client.get("/api/v1/datos/estado", headers=admin_headers).json()
    assert {f["tabla"] for f in estado["fuentes"]} >= {"casos_oficiales", "registros_clima", "predicciones"}

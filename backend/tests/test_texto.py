"""Utilidades de texto compartidas."""
import pytest

from app.core.texto import numero_es, separar_lista
from app.models import Enfermedad


@pytest.mark.parametrize(("texto", "esperado"), [
    ("fiebre, Dengue ,, tos ", ["fiebre", "Dengue", "tos"]),
    ("", []),
    (None, []),
])
def test_separar_lista(texto, esperado):
    assert separar_lista(texto) == esperado


def test_separar_lista_normaliza():
    assert separar_lista("a ,b", str.upper) == ["A", "B"]


@pytest.mark.parametrize(("valor", "decimales", "miles", "esperado"), [
    (118.45, 1, False, "118,5"),
    (1234.5, 0, True, "1.234"),
    (1234567.891, 2, True, "1.234.567,89"),
    (0, 1, False, "0,0"),
    (None, 1, False, "—"),
])
def test_numero_es(valor, decimales, miles, esperado):
    assert numero_es(valor, decimales, miles) == esperado


def test_listas_de_la_enfermedad():
    e = Enfermedad(codigo="X", nombre="X", terminos_busqueda="Fiebre, TOS", codigos_sivigila="210, 220",
                   categorias_farmacia="antigripales,REPELENTES", recomendaciones="Uno\n\n  Dos  \n")
    assert e.lista_terminos == ["fiebre", "tos"]
    assert e.lista_codigos_sivigila == ["210", "220"]
    assert e.lista_categorias_farmacia == ["ANTIGRIPALES", "REPELENTES"]
    assert e.lista_recomendaciones == ["Uno", "Dos"]

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Pagina[T](BaseModel):
    items: list[T]
    total: int
    offset: int
    limit: int


class Mensaje(BaseModel):
    mensaje: str

"""Catalogue CRUD routers (generated with the factory)."""
from volcano.gateway.routers.crud import build_crud_router
from volcano.schemas.catalog import (
    DiseaseCreate,
    DiseaseOut,
    DiseaseUpdate,
    MunicipalityCreate,
    MunicipalityOut,
    MunicipalityUpdate,
    PharmacyCreate,
    PharmacyOut,
    PharmacyUpdate,
    VolcanicEventCreate,
    VolcanicEventOut,
    VolcanicEventUpdate,
)
from volcano.services.catalog import DiseaseService, MunicipalityService, PharmacyService, VolcanicEventService

municipalities = build_crud_router(
    prefix="/municipalities", tag="Municipalities", service=MunicipalityService,
    create_schema=MunicipalityCreate, update_schema=MunicipalityUpdate, out_schema=MunicipalityOut,
)

diseases = build_crud_router(
    prefix="/diseases", tag="Diseases", service=DiseaseService,
    create_schema=DiseaseCreate, update_schema=DiseaseUpdate, out_schema=DiseaseOut,
)

pharmacies = build_crud_router(
    prefix="/pharmacies", tag="Pharmacies", service=PharmacyService,
    create_schema=PharmacyCreate, update_schema=PharmacyUpdate, out_schema=PharmacyOut,
    public_read=False, filters=("municipality_id",),
)

volcanic_events = build_crud_router(
    prefix="/volcanic-events", tag="Volcanic events", service=VolcanicEventService,
    create_schema=VolcanicEventCreate, update_schema=VolcanicEventUpdate, out_schema=VolcanicEventOut,
    filters=("municipality_id",), author_field="recorded_by_id",
)

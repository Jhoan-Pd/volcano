"""Disease outbreak predictor for Pasto and the Galeras volcano area (Nariño, Colombia).

Three services share this package and run in one container:

    volcano.gateway   public REST API (FastAPI), SSE bridge for training progress
    volcano.engine    gRPC prediction engine: models in memory, training, forecasts, scenarios
    volcano.realtime  WebSocket hub: live alerts, the scenario simulator and presence

Domain code (models, services, ml, sources) is shared; each service imports only what it uses.
"""
__version__ = "3.0.0"

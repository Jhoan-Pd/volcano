#!/usr/bin/env bash
# Genera el código Python de gRPC a partir del contrato .proto.
# Se ejecuta desde backend/ con -I . para que los imports generados sean absolutos
# (from app.motor.protos import prediccion_pb2) y funcionen como paquete.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m grpc_tools.protoc -I . \
  --python_out=. --grpc_python_out=. --pyi_out=. \
  app/motor/protos/prediccion.proto
echo "Código gRPC generado en app/motor/protos/"

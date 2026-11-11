#!/usr/bin/env bash
# Generate the Python gRPC code from the .proto contract.
#
# The contract lives in proto/volcano/engine/v1/engine.proto (its path mirrors the protobuf package,
# as buf and the style guide recommend). protoc derives Python imports from that path, so the code is
# generated in a temporary folder and moved into volcano/rpc/ with its import rewritten:
#   from volcano.engine.v1 import engine_pb2  →  from volcano.rpc import engine_pb2
set -euo pipefail
cd "$(dirname "$0")/.."
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT
python -m grpc_tools.protoc -I proto \
  --python_out="$out" --grpc_python_out="$out" --pyi_out="$out" \
  proto/volcano/engine/v1/engine.proto
for f in engine_pb2.py engine_pb2.pyi engine_pb2_grpc.py; do
  sed 's/from volcano\.engine\.v1 import engine_pb2/from volcano.rpc import engine_pb2/' \
    "$out/volcano/engine/v1/$f" > "volcano/rpc/$f"
done
echo "gRPC code generated in volcano/rpc/"

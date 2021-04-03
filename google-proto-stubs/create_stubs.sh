#!/bin/bash
# Copyright 2021 Google
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -x -e -o pipefail

GOOGLEAPIS_DIR=${GOOGLEAPIS_DIR:-"/tmp/googleapis"}
GOOGLEAPIS_SHA="8ff7d794576311d3d68d4df2ac6da93bbfcd7476"

orig_dir=$PWD

if [ ! -d "$GOOGLEAPIS_DIR" ]; then
    git clone https://github.com/googleapis/googleapis.git $GOOGLEAPIS_DIR
fi
cd $GOOGLEAPIS_DIR

# Pull in changes and switch to requested branch
(
    cd $GOOGLEAPIS_DIR
    git fetch --all
    git checkout $GOOGLEAPIS_SHA
)

if [ ! -d "venv/" ]; then
    python3 -m venv venv/
fi
source venv/bin/activate
pip install -U pip mypy-protobuf grpcio-tools

rm -rf gen/
mkdir gen/

# Invokes protoc to output all dependent files of trace/metric service protos.
proto_files=$(
    python3 -m grpc_tools.protoc \
        -I . \
        --include_imports \
        --include_source_info \
        google/devtools/cloudtrace/v2/tracing.proto \
        google/monitoring/v3/metric_service.proto \
        -o /dev/stdout 2> /dev/null |
    $orig_dir/fds_to_files.py |
    grep -v 'google\/protobuf' |
    xargs
)
python3 -m grpc_tools.protoc -I . --mypy_out=gen $proto_files

mkdir -p gen/google/cloud/trace_v2 gen/google/cloud/monitoring_v3
mv gen/google/devtools/cloudtrace/v2 gen/google/cloud/trace_v2/proto
mv gen/google/monitoring/v3 gen/google/cloud/monitoring_v3/proto

find gen -type d -empty -delete
perl -i -p -e \
    's/google\.devtools\.cloudtrace\.v2/google\.cloud\.trace_v2\.proto/; \
    s/google\.monitoring\.v3/google\.cloud\.monitoring_v3\.proto/' \
    $(find gen/ -name "*.pyi")

rm -rf $orig_dir/src/google
cp -R gen/* $orig_dir/src/.
touch $orig_dir/src/google/py.typed

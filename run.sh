#!/bin/bash
set -e

docker build -t "invokeai-presets" .
docker run -it --rm \
    --cap-drop=ALL \
    -v "$(pwd):/home/invokeaiuser" \
    -v "$(pwd)/docker:/home/invokeaiuser/docker:ro" \
    -v "/var/run/docker.sock:/var/run/docker.sock" \
    --name running-invokeai-presets "invokeai-presets" "$@" && \
    docker exec -it running-invokeai-presets pip install .

@echo off
setlocal enabledelayedexpansion

REM Build the Docker image
docker build -t invokeai-models .

REM Run the Docker container with the specified arguments
docker run -it --rm ^
    --cap-drop=ALL ^
    -v %cd%:/home/invokeaiuser ^
    -v %cd%/docker:/home/invokeaiuser/docker:ro ^
    -v \\.\pipe\docker_engine:/var/run/docker.sock ^
    --name running-invokeai-models invokeai-models %* && ^
    docker exec -it running-invokeai-models pip install .

pause
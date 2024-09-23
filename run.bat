@echo off
setlocal enabledelayedexpansion

REM Build the Docker image
docker build -t invokeai-presets .

REM Run the Docker container with the specified arguments
docker run -it --rm ^
    --cap-drop=ALL ^
    -v %cd%:/home/invokeaiuser ^
    -v %cd%/docker:/home/invokeaiuser/docker:ro ^
    -v \\.\pipe\docker_engine:/var/run/docker.sock ^
    --name running-invokeai-presets invokeai-presets %* && ^
    docker exec -it running-invokeai-presets pip install .

pause
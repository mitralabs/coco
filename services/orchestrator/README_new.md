## Build the docker container:
`docker build -t orchestrator .`

## Run the docker container:
`docker run -d -p 3030:8000 -v $(pwd)/../../python_sdk:/app/python_sdk -v $(PWD)/../_data/audio_files:/data --name orchestrator orchestrator`
# Downloading a model:
- Go to [huggingface](https://huggingface.co/ggerganov/whisper.cpp/tree/main) and download a `.bin` file, with the model you'd like to use.
- Place the `.bin`file in the [whisper_cpp](/base/_data/models/whisper_cpp/)-folder

# Setting the model
- This is currently done in the .env file. Make sure you have the model downloaded (see previous step). Name the variable without the '.bin' extension.

# Building the container
### With CPU
```
docker build -t whisper-cpp .
```
### With GPU Support
```
docker build -f Dockerfile_GPU -t whisper-cpp-gpu .
```

# Running the container. Note: use ${PWD} in the docker run commands, if you run on windows.
### With CPU
```
docker run -d -p 3031:8000 -v $(pwd)/app:/app -v $(pwd)/../../_data/models/whisper_cpp:/whisper.cpp/models --name whisper-cpp whisper-cpp
```
### With GPU Support
```
docker run -d -p 3031:8000 --gpus all -v $(pwd)/app:/app -v $(pwd)/../../_data/models/whisper_cpp:/whisper.cpp/models --name whisper-cpp-gpu whisper-cpp-gpu
```
Note: Make sure to have the [Nvidia Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html#installation) installed.
You might need to Configure Docker to use Nvidia driver as well:
Note 2: It might be possible that your Docker Container is Memory restricted. And doesn't run. Try adding the flag --memory=0

```
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

# Testing the Transcription
```
curl -X POST -H "X-API-Key: your_api_key" -F "audio_file=@path-to-audio-file.wav" http://localhost:3031/transcribe/ > output.json
```

# ToDo
- [ ] Include the model in the API Call. This will require a default model as well.
- [ ] Include a make command for machines with CoreML (Apple Silicon)
- [ ] Improve the JSON Response

# Random Note
- large-v3-turbo-q5_0 didn't work within the docker container.
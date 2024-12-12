# Preparation
- Make sure to have the directory /models in the /_data directory. And have a directory /whisper_cpp in it.
- Copy all the content from the whisper.cpp models directory there


# Downloading a model:
- cd into the directory base/_data/models/whisper_cpp
- run the command `sh ./download-ggml-model.sh tiny` with tiny being the model in question. 

# Setting the model
- This is currently done in the .env file. Make sure the corresponding model is already downloaded. Further: just name it without the '.bin' extension.

# Building the container
### With CPU
```
docker build -t whisper-cpp .
```
### With GPU Support
```
docker build -f Dockerfile_GPU -t whisper-cpp-gpu .
```

# Running the container
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
- [ ] Include a make command for machines with GPU support. Currently only running on CPU. (Same goes for CoreML / Apple Support)
- [ ] Improve the documentary, especially the models part at the beginning.

# Random Note
- large-v3-turbo-q5_0 didn't work within the docker container.
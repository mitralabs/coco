# Downloading a model:
- cd into the directory base/_data/models/whisper_cpp
- run the command `sh ./download-ggml-model.sh tiny` with tiny being the model in question. 

# Setting the model
- This is currently done in the .env file. Make sure the corresponding model is already downloaded. Further: just name it without the '.bin' extension.

# Building the container
```
docker build -t whisper-cpp .
```

# Running the container
```
docker run -d -p 3031:8000 -v $(PWD)/app:/app -v $(PWD)/../../_data/models/whisper_cpp:/whisper.cpp/models --name whisper-cpp whisper-cpp
```

# Testing the Transcription
```
curl -X POST -H "X-API-Key: your_api_key" -F "audio_file=@path-to-audio-file.wav" http://localhost:3031/transcribe/ > output.json
```

# ToDo
- [ ] Include the model in the API Call. This will require a default model as well.
- [ ] Include a make command for machines with GPU support. Currently only running on CPU. (Same goes for CoreML / Apple Support)
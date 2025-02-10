# coco

This is the coco Repository. 
Currently developed by a small team, funded by [hessian.ai](https://hessian.ai), for what we are truely grateful!

You will need to have some/basic knowledge in the latter domains, to get this Repo up and running (or the motivation to learn them).
1. `.git` and how to work with opensource Repositories, following their `README.md`
2. Docker
3. The Command Line / Terminal

## Step by Step Guide to run coco on a fresh Mac:
*Skip all steps not needed on your machine*

-> Further steps are needed to install pip. as well as the requirements.txt (for huggingface cli, uvicorn, ...)


1. Download [Ollama](https://ollama.com)
2. [Install Homebrew](https://brew.sh)
3. Install [Docker Desktop](https://docs.docker.com/desktop/) (Note: Other Docker Engines might work fine as well.)
4. Install ffmpeg (audio library) via the commandline `brew install ffmpeg`
5. Install git via the commandline `brew install git`
6. Install cmake `brew install cmake`
7. Git clone the whisper.cpp Repository (needed for Audio Transcription) (Note: **Do not clone whisper.cpp into this repository.**)
    - cd with your terminal to a destination where you want to save the [whisper.cpp Repo](https://github.com/ggerganov/whisper.cpp.git)
    - `git clone https://github.com/ggerganov/whisper.cpp.git` 
    - Follow the README to download a model (we suggest whisper large v3 turbo.)
    - For our german friends we suggest the [german](https://huggingface.co/cstr/whisper-large-v3-turbo-german-ggml) whisper model. Use `huggingface-cli download cstr/whisper-large-v3-turbo-german-ggml --local-dir models`
    - Now build the project with `cmake`. -> There are options to build the project with CUDA, CoreML, ... support.


#### Now there is just two more things to do:
1. Follow [this ReadMe](/services/README.md) to install the additional services.
2. Set Up your Coco Device, by following [this ReadMe](/coco/README.md)
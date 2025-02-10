# coco

This is the coco Repository. 
Currently developed by a small team, funded by [hessian.ai](https://hessian.ai), for what we are truely grateful!

You will need to have some/basic knowledge in the latter domains, to get this Repo up and running (or the motivation to learn them).
1. `.git` and how to work with opensource Repositories, following their `README.md`
2. Docker
3. The Command Line / Terminal

## Step by Step Guide to run coco on a fresh Mac:
*Skip all steps not needed on your machine*



1. Install [Ollama](https://ollama.com)
2. [Install Homebrew](https://brew.sh) -> Make sure to follow all the instructions in your commandline during the installation process.
3. Install [Docker Desktop](https://docs.docker.com/desktop/) (Note: The Docker Engine without Desktop Client might work fine as well.)
4. Install ffmpeg (audio library) via the commandline `brew install ffmpeg git cmake`

7. Install pip via `python3 -m pip install --upgrade pip`
8. Git clone the whisper.cpp Repository (needed for Audio Transcription) (Note: **Do not clone whisper.cpp and coco into each other.**)
    - cd with your terminal to a destination where you want to save the [whisper.cpp Repo](https://github.com/ggerganov/whisper.cpp.git)
    - `git clone https://github.com/ggerganov/whisper.cpp.git` 
    - Now build the project with `cmake`. -> There are options to build the project with CUDA, CoreML, ... support.
8. Now git clone this repo `git clone https://github.com/mitralabs/coco.git` (Note: **Do not clone whisper.cpp and coco into each other.**)


## Go to /services (this part of the readme will be transfered there)

Well done. Your basics are setup. Now we need to setup the backend. Open a terminal, preferably in your Development Environment, within the coco/services Directory `cd coco/services`

9. Now you need to find the `main`executable within the /whisper.cpp Directory. It is most likely under this path /whisper.cpp/build/bin. Copy the absolute path of the file. You can output the absolute path of a folder on your system by opening a terminal within that folder (right click, and open terminal) and typing `pwd`. This will probably output something like this `/Users/coco/path/to/whisper.cpp/build/bin`.
9. 


**Set Up Whisper BackEnd**
`nohup python -m uvicorn transcription.whisper_cpp.app.main_out:app --host 0.0.0.0 --port 8000 --reload --log-level debug > transcription/uvicorn.log 2>&1 &`
Runs the uvicorn server in the background, even when the terminal is closed. To stop it, first find the id using:
`ps aux | grep uvicorn`
Then stop it with:
`kill <PID>`

## Download Models
**Download a model from ollama**

**Download a Whisper Model**
- Follow the README to download a model (we suggest whisper large v3 turbo.)
    - For our german friends we suggest the [german](https://huggingface.co/cstr/whisper-large-v3-turbo-german-ggml) whisper model. Use `huggingface-cli download cstr/whisper-large-v3-turbo-german-ggml --local-dir models`

#### Now there is just two more things to do:
1. Follow [this ReadMe](/services/README.md) to install the additional services.
2. Set Up your Coco Device, by following [this ReadMe](/coco/README.md)
# coco

---
# This is under active development. The readme will be done by Feb 11th.
---

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
3. Install [Docker Desktop](https://docs.docker.com/desktop/) (Note: The Docker Engine without Desktop Client might work fine as well.) Installing means opening and running through the wizard after downloading!
4. Install ffmpeg (audio library) via the commandline `brew install ffmpeg git cmake`

7. Install pip via `python3 -m pip install --upgrade pip`

8. Now git clone this repo `git clone https://github.com/mitralabs/coco.git` (Note: **Do not clone whisper.cpp and coco into each other.**)

8. Git clone the whisper.cpp Repository (needed for Audio Transcription) (Note: **Do not clone whisper.cpp and coco into each other.**)
    - cd with your terminal to a destination where you want to save the [whisper.cpp Repo](https://github.com/ggerganov/whisper.cpp.git)
    - `git clone https://github.com/ggerganov/whisper.cpp.git` 
    - Now build the project with `cmake`. -> There are options to build the project with CUDA, CoreML, ... support.


Now you need to find the file named `whisper-cli` within the /whisper.cpp Directory. It is most likely under the path /whisper.cpp/build/bin. Copy the absolute path of the file. You can output the absolute path of a folder on your system by opening a terminal within that folder (right click, and open terminal) and typing `pwd`. This will probably output something like this `/Users/coco/path/to/whisper.cpp/build/bin`.

Other option: Just find the file within your file system right click on it -> information -> right click on the ort/location and "copy the pathname" -> make sure to add the name of the file itself, since only the path is copied.


## Go to /services (this part of the readme will be transfered there)

Well done. Your basics are setup. Now we need to setup the backend. Open a terminal, preferably in your Development Environment, within the coco/services Directory `cd coco`

- `python3 -m venv venv-coco`
- `source venv-coco/bin/activate` (-> this should suffice in the services directory)
- `pip install -r requirements.txt` (is it possible to include a path? should be...)

**Download a Whisper Model**
- Follow the README to download a model (we suggest whisper large v3 turbo.)
    - For our german friends we suggest the [german](https://huggingface.co/cstr/whisper-large-v3-turbo-german-ggml) whisper model. Use `huggingface-cli download cstr/whisper-large-v3-turbo-german-ggml --local-dir models`

- Or by using visting the [site](https://huggingface.co/cstr/whisper-large-v3-turbo-german-ggml/tree/main) and downloading the .bin file and placing it into the models directory of the whisper.cpp repo. 


Now there is a env.txt file within the services folder. Please open it, since we need to make some adjustments here.

Then, run `mv env.txt .env` (no worries, we didn't delete the file, it is just not displayed under normal circumstances)



**Set Up Whisper BackEnd**
`nohup python -m uvicorn transcription.whisper_cpp.app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug > transcription/uvicorn.log 2>&1 &`


Runs the uvicorn server in the background, even when the terminal is closed. To stop it, first find the id using:
`ps aux | grep uvicorn`
Then stop it with:
`kill <PID>`

## Download Models
**Download a chat model from ollama**
**Download the embedding model from ollama**

## Things that didn't work yet.
- Need to set the API Key for Ionos
- 

#### Now there is just two more things to do:
1. Follow [this ReadMe](/services/README.md) to install the additional services.
2. Set Up your Coco Device, by following [this ReadMe](/coco/README.md)
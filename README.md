# coco

This is the coco Repository. <br>
Currently developed by a small team, and funded by [hessian.ai](https://hessian.ai).

You will need to have some/basic knowledge in the latter domains, to get this Repo up and running (or the motivation to learn them).

1. The command line / terminal. You don't need any Coding Environment, if you don't plan on building the hardware yourself.
2. Github and `.git`
3. Docker

-> We plan on recording a video on how to set this project up. So stay tuned for that.

## Step by Step Guide to run coco on a Mac\*:

> We will evaluate this guide for Windows and Linux machines as well.

_Skip all steps not needed on your machine. Most likely the "Basic Setup"_

### Basic Setup:

1. Install [Ollama](https://ollama.com)
2. [Install Homebrew](https://brew.sh) -> Make sure to follow all the instructions in your commandline during the installation process.
3. Install [Docker Desktop](https://docs.docker.com/desktop/) (Note: The Docker Engine without Desktop Client might work fine as well.) Installing means opening and running through the wizard after downloading!
4. Install ffmpeg (audio library), git, and cmake via the commandline `brew install ffmpeg git cmake`
5. Install pip via `python3 -m pip install --upgrade pip`
6. Install [VS Code](https://code.visualstudio.com). It makes most easier, and is needed for the coco firmware. (For convenience, add it to path by using the `>shell command` within vs code)

### Middleware Setup:

(Note: **Do not clone whisper.cpp and coco into each other.**)

1. Now open a terminal in the directory you want to clone coco and whisper.cpp in
2. Git clone this repo `git clone https://github.com/mitralabs/coco.git`
3. Git clone the [whisper.cpp Repo](https://github.com/ggerganov/whisper.cpp.git) Repository (Audio Transcription Engine)
   - `git clone https://github.com/ggerganov/whisper.cpp.git`
   - Now build the project with `cmake` according to the instructions on Github. -> There are options to build the project with CUDA, CoreML, ... support as well. Have a look if that interests you.
4. Follow the README to download a model (we suggest whisper large v3 turbo.)
   - For our german friends we suggest the [german](https://huggingface.co/cstr/whisper-large-v3-turbo-german-ggml/tree/main) whisper model. Just download the `ggml-model.bin`file and place it in the /models folder inside of the /whisper.cpp directory.<br>
     Advanced: Run this command in a terminal in the /whisper.cpp directory: `huggingface-cli download cstr/whisper-large-v3-turbo-german-ggml --local-dir models`
5. Download a chat model from [ollama](https://www.ollama.com), we currently suggest the mistral series (mistral / mistral-nemo / mistral-small) depending on your setup.
6. Download an embedding model from ollama as well, we currently suggest (nomic-embed-test / bge-m3).

> Note to team: It is currently not trivial to change the models within the main code. Be sure to correct this.

### Final Setup:

Well done. Your basics are setup. Now we need to setup the backend, and potentially the coco device.

1. Follow [this ReadMe](/services/README.md) to install the additional services.
2. Set Up your Coco Device, by following [this ReadMe](/coco/firmware/README.md)

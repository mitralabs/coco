# coco

This is the coco Repository. <br>
The project was funded by [hessian.ai](https://hessian.ai) and developed by a small team (see [our website](www.mitra-labs.ai) for more information.)

You will need to have some/basic knowledge in the latter domains, to get this Repo up and running (or the motivation to learn them).

1. The command line / terminal. You don't need any Coding Environment, although it's helpful.
2. Github and `.git`
3. Docker

-> We plan on recording a video on how to set this project up. So stay tuned for that.

## Step by Step Guide to run coco on a **Mac**:
>Note: We developed on Mac OS. So you might run into troubles on different OSes. Feel free to [contact us](mailto:coco@mitra-labs.ai), and we try to help as much as possible.
*Skip all steps not needed on your machine. Most likely the "Basic Setup"*

### Basic Setup:

1. [Install Homebrew](https://brew.sh) -> Make sure to follow all the instructions in your commandline during the installation process.
2. Install [Docker Desktop](https://docs.docker.com/desktop/) (Note: The Docker Engine without Desktop Client might work fine as well.) Installing means opening and running through the wizard after downloading!
3. Install ffmpeg (audio library), git, and cmake via the commandline `brew install ffmpeg git cmake`
4. Install pip via `python3 -m pip install --upgrade pip`
5. Install [VS Code](https://code.visualstudio.com). It makes most easier, and is needed for the coco firmware. (For convenience, add it to path by using the `>shell command` within vs code)

### Middleware Setup:

1. Install [Ollama](https://ollama.com)
2. Download a chat model from [ollama](https://www.ollama.com), make sure that it supports *tool use* or *function calling*. We strongly suggest testing different models to find one that best suits your hardware.
3. Download an embedding model from ollama as well, we currently suggest *bge-m3*

### Final (Privat Backend) Setup:

1. Now open a terminal in the directory you want to clone coco to.
2. Git clone this repo `git clone https://github.com/mitralabs/coco.git`
3. cd into the "services" subdirectory `cd coco/services`
4. Follow [this ReadMe](/services/README.md) to install the additional services.

Well done. Now and lastly, to set up your coco device, follow [this ReadMe](/coco/firmware/README.md)
>**This Repo is under active refactoring. It will develop from a "full" repo, with self developed (Gradio) Frontend to a MCP Server which can be connected to different frontends. This decision was made due to the fact that the core value within this repo lies in coco, a wearable recording device and it's corresponding backend.**


# coco

coco is an open source recording device that's supposed to not forget. Every recorded conversation is sent to the backend, transcribed, stored in a database and made available to a LLM via Chatinterface. If you want to, and have some compute, fully private/local.<br>

So far, it was developed by a small team, with lots of fun (see [our website](www.mitra-labs.ai) for more information).<br>

A substantial part of the development was funded by [hessian.ai](https://hessian.ai), thank you for making this possible!

## Step by Step Guide to run coco on a **Mac**:
>Note: We developed on Mac OS. So you might run into troubles on different OSes. Feel free to [contact us](mailto:coco@mitra-labs.ai), and we try to help as much as possible.
*Skip all steps not needed on your machine. Most likely the "Basic Setup"*

### Before you begin:
You need Git, Docker, ffmpeg, pip and cmake installed. See the later, if that is not the case:

- [Install Homebrew](https://brew.sh), it makes a lot easier. -> Make sure to follow all the instructions in your commandline during the installation process.
- Install ffmpeg (audio library), git, and cmake via the commandline `brew install ffmpeg git cmake`
- Install [Docker Desktop](https://docs.docker.com/desktop/) (Note: The Docker Engine without Desktop Client might work fine as well.) Installing means opening and running through the wizard after downloading!
- Install pip via `python3 -m pip install --upgrade pip`
- Optional: Install [VS Code](https://code.visualstudio.com). It is needed for the coco firmware. (For convenience, add it to path by using the `>shell command` within vs code)

### Middleware Setup:
#### Chat Interface
You can use whatever Chatinterface you like that supports the MCP Protocol aka acts as a MCP Client. See [here](https://modelcontextprotocol.io/introduction) for more information.

**If you plan on using Ollama as Inference Engine (see below)**, we suggest **[Librechat](https://github.com/danny-avila/LibreChat)** as Chatinterface since it supports MCP. Otherwise, it's probably easiest to start with [Claude Desktop](https://claude.ai/download). We added Instructions for the setup of both. Just continue below.

#### LLM Inference & Embeddings
1. Install [Ollama](https://ollama.com)
2. Download a chat model from [ollama](https://www.ollama.com), make sure that it supports *tool use* or *function calling*. We strongly suggest testing different models to find one that best suits your hardware.
3. Download an embedding model from ollama as well, we currently suggest *bge-m3*

### Final (Backend) Setup:
1. Now open a terminal in the directory you want to clone coco to.
2. Git clone this repo `git clone https://github.com/mitralabs/coco.git`
3. cd into the "services" subdirectory `cd coco/services`
4. Follow [this ReadMe](/services/README.md) to install the additional services.

Well done. Now and lastly, to set up your coco device, follow [this ReadMe](/coco/firmware/README.md)

## Additional Notes:
1. [Nico Stellwag](https://nicolasstellwag.com) wrote a paper on the RAG pipeline. The final code before submisson can be found on the *hack-nico* Branch in the [RAG](test/rag/)-Folder.
2. All the code that was developed during the hessian.ai funding period is on the *hessian-ai* branch.
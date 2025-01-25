"""
title: Ollama Pipe
authors: mitra labs
author_url: https://github.com/mitralabs/coco
version: 0.1.0
license: MIT
"""

import requests
import json
import time
from typing import List, Union, Generator, Iterator
from pydantic import BaseModel, Field
from open_webui.utils.misc import pop_system_message


class Pipe:
    class Valves(BaseModel):
        pass

    def __init__(self):
        self.type = "manifold"
        self.id = "coco"
        self.name = "coco/"
        pass

    def pipes(self) -> List[dict]:
        return [
            {"id": "phi3:3.8b", "name": "phi3"},
            {"id": "gemma2:2b", "name": "gemma2"},
        ]

    def pipe(self, body: dict) -> Union[str, Generator, Iterator]:
        system_message, messages = pop_system_message(body["messages"])
    
        # Alternative System Message, which will be exchanged for a request to /coco
        system_message = {'role': 'system', 'content': "write strictly in french"}
        messages.append(system_message)
        
        payload = {
            "model": body["model"][body["model"].find(".") + 1 :],
            "messages": messages,
            "stream": body.get("stream", False),
        }

        url = "http://host.docker.internal:11434/api/chat"

        try:
            if body.get("stream", False):
                return self.stream_response(url, payload)
            else:
                return self.non_stream_response(url, payload)
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return f"Error: Request failed: {e}"
        except Exception as e:
            print(f"Error in pipe method: {e}")
            return f"Error: {e}"

    def stream_response(self, url, payload):
        try:
            with requests.post(url, json=payload, timeout=(3.05, 60)) as response:
                
                if response.status_code != 200:
                    raise Exception(f"HTTP Error: {response.status_code}: {response.text}")

                for line in response.iter_lines():
                    if line:
                        line = line.decode("utf-8")
                        try:
                            data = json.loads(line)
                            message = data.get("message", "")
                            yield message.get("content", "")
                            time.sleep(0.01)

                        except json.JSONDecodeError:
                            print(f"Failed to parse JSON: {line}")
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            yield f"Error: Request failed: {e}"
        except Exception as e:
            print(f"General error in stream_response method: {e}")
            yield f"Error: {e}"

    def non_stream_response(self, url, payload):
        try:
            response = requests.post(url, json=payload, timeout=(3.05, 60))

            if response.status_code != 200:
                raise Exception(f"HTTP Error {response.status_code}: {response.text}")

            res = response.json()
            message = res.get("message", "")
            content = message.get("content", "")
            return content
        
        except requests.exceptions.RequestException as e:
            print(f"Failed non-stream request: {e}")
            return f"Error: {e}"
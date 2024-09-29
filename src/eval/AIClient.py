from openai import OpenAI
import json
from anthropic import AnthropicVertex

class BaseAIClient():
    def __init__(self) -> None:
        pass

    def inference(self, messages, n):
        raise NotImplementedError("Please Use the correct client, This is the base class!")

class OpenAIClient(BaseAIClient):
    """
    you can use this api as openai client or local model deployed on your own machine with vllm, ollama, etc.
    or any online model with compatible api, for example, deepseek.
    """
    def __init__(self, url, key, model) -> None:
        
        self.client = OpenAI(
            base_url=url,
            api_key=key,
        )
        self.model = model

    def inference(self, messgaes, n):
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messgaes,
            n=n
        )
        return [completion.choices[i].message.content.strip() for i in range(n)]
    

class VertextAIClient(BaseAIClient):
    """
    this api is for anthropic vertex ai, please refer to the official website for more details.
    """
    def __init(self, region, project_id, model_name):
        self.region = region
        self.project_id = project_id
        self.model_name = model_name
        self.client = AnthropicVertex(region=region, project_id=project_id)

    def infrence(self, messages, n):

        message = self.client.messages.create(
            max_tokens=1024,
            temperature=0.5,
            messages=messages,
            model=self.model_name,
        )
        return [message.content[0].text]


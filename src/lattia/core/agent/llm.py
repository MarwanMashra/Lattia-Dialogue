import os
import time
from typing import Type, cast

from openai import AzureOpenAI, OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel


class LLM:
    def __init__(self, model_name: str = "gpt-4.1-2025-04-14"):
        self.model_name = model_name
        if api_key := os.getenv("OPENAI_API_KEY"):
            self.client = OpenAI(api_key=api_key)
        elif (api_key := os.getenv("AZURE_OPENAI_API_KEY")) and (
            endpoint := os.getenv("AZURE_OPENAI_ENDPOINT")
        ):
            self.client = AzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version=os.getenv("OPENAI_API_VERSION", "2024-10-21"),
            )
        else:
            raise ValueError(
                "No OpenAI API key or Azure OpenAI credentials found. "
                "Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables."
            )

    def send_with_structured_response(
        self,
        response_format: Type[BaseModel],
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 3000,
        verbose: bool = False,
    ) -> BaseModel:
        t0 = time.time()
        completion = self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=cast(list[ChatCompletionMessageParam], messages),
            response_format=response_format,
            max_completion_tokens=max_tokens,
            temperature=temperature,
        )
        if verbose:
            print(f"LLM response time: {time.time() - t0:.2f} seconds")
            print(completion.usage)

        response = completion.choices[0].message
        if response.parsed:
            return response.parsed
        elif response.refusal:
            raise ValueError("LLM response formatted refused : %s", response.refusal)
        else:
            raise ValueError("LLM response is not in the expected format.")

    def send(
        self,
        messages: list[ChatCompletionMessageParam],
        temperature: float = 0.7,
        max_tokens: int = 3000,
    ):
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=False,
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )
        return response.choices[0].message.content

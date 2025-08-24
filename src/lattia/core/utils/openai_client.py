import os

from openai import AzureOpenAI, OpenAI


def get_openai_like_client() -> AzureOpenAI | OpenAI:
    """
    Returns (client, vendor), where vendor is 'openai' or 'azure'.
    Prefers OPENAI_API_KEY if present, otherwise AZURE_*.
    """
    if api_key := os.getenv("OPENAI_API_KEY"):
        return OpenAI(api_key=api_key)

    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if api_key and endpoint:
        api_version = os.getenv("OPENAI_API_VERSION", "2024-10-21")
        return AzureOpenAI(
            api_key=api_key, azure_endpoint=endpoint, api_version=api_version
        )

    raise ValueError(
        "No OpenAI API key or Azure OpenAI credentials found. "
        "Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT."
    )

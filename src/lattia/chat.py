from pydantic import BaseModel, Field

from .core.llm import LLM


class CoutryInfo(BaseModel):
    name: str = Field(..., description="Name of the country")
    capital: str = Field(..., description="Capital city of the country")
    population: int = Field(..., description="Population of the country")
    area: float = Field(..., description="Area of the country in square kilometers")

    def __str__(self):
        return f"{self.name} (Capital: {self.capital}, Population: {self.population}, Area: {self.area} km²)"


def main():
    llm = LLM()

    llm_response = llm.send_with_structured_response(
        response_format=CoutryInfo,
        messages=[{"role": "user", "content": "Tell me about France."}],
        temperature=0.5,
        max_tokens=500,
    )
    print(llm_response)

    llm_response = llm.send(
        messages=[{"role": "user", "content": "Tell me about France."}],
        temperature=0.5,
        max_tokens=10,
    )
    print(llm_response)


if __name__ == "__main__":
    main()

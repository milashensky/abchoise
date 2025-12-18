from abc import ABC, abstractmethod
from openai import OpenAI


class LLMError(Exception):
    pass


class LLMAdapter(ABC):
    @abstractmethod
    def generate_options(self, prompt: str, history: list, rejected: list = None) -> tuple[str, str]:
        pass


class OpenAIAdapter(LLMAdapter):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    SYSTEM_PROMPT = """You are a creative assistant that generates options based on given criteria.
When history is provided, use an exploitation/exploration balance:
- Option 1 should EXPLOIT: go deeper in the direction of previously selected options
- Option 2 should EXPLORE: try a different area of the criteria space
Always respond with exactly 2 options, one per line, without numbering or prefixes."""

    def generate_options(self, prompt: str, history: list, rejected: list = None) -> tuple[str, str]:
        history_text = ""
        if history:
            history_text = f"\n\nPreviously selected options (use as positive examples): {', '.join(history)}"
        rejected_text = ""
        if rejected:
            rejected_text = f"\n\nDeprioritize these options (user rejected both): {', '.join(rejected)}"
        user_content = f"{prompt}{history_text}{rejected_text}\n\nGenerate exactly 2 options, one per line."
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ]
            )
        except Exception as e:
            raise LLMError(f"API call failed: {e}") from e
        lines = response.choices[0].message.content.strip().split('\n')
        opt_a = lines[0].strip()
        opt_b = lines[1].strip() if len(lines) > 1 else ""
        return opt_a, opt_b

from enum import StrEnum

class LLM(StrEnum):
    """
    Determines which models are currently available.
    """
    MOCK       = "MOCK"
    GPT4o      = "gpt-4o"
    GPTo4_MINI = "gpt-o4-mini"
    LLAMA      = "llama-3.3-70b-versatile"
    DEEPSEEK   = "deepseek-r1-distill-llama-70b"

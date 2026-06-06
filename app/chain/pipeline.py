from __future__ import annotations

from transformers import pipeline as hf_pipeline

from app.chain.runnable import Runnable
from app.chain.steps import (
    DataFetcher,
    IntentClassifier,
    PromptBuilder,
    ResponseFormatter,
    SmolLMStep,
)

_pipeline_cache: Runnable | None = None


def build_ai_pipeline(llm) -> Runnable:
    return (
        IntentClassifier()
        | DataFetcher()
        | PromptBuilder()
        | SmolLMStep(llm=llm)
        | ResponseFormatter()
    )


def get_pipeline() -> Runnable:
    global _pipeline_cache
    if _pipeline_cache is None:
        llm = hf_pipeline(
            "text-generation",
            model="HuggingFaceTB/SmolLM-135M-Instruct",
        )
        _pipeline_cache = build_ai_pipeline(llm)
    return _pipeline_cache

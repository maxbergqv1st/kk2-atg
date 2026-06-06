from app.chain import get_pipeline
from app.chain.steps import AiPipelineResponse


def ask_question(question: str) -> AiPipelineResponse:
    pipeline = get_pipeline()
    return pipeline.invoke(question)

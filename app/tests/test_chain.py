from app.chain.steps import (
    Intent,
    IntentClassifier,
    IntentClassifierOutput,
    DataFetcherOutput,
    PromptBuilder,
    PromptBuilderOutput,
    SmolLMOutput,
    ResponseFormatter,
    AiPipelineResponse,
)


def test_intent_classifier_horse_stats():
    """IntentClassifier ska klassificera fragan som HORSE_STATS."""
    classifier = IntentClassifier()
    result = classifier.invoke("Vilken hast har bast vinstprocent?")

    assert isinstance(result, IntentClassifierOutput)
    assert result.intent == Intent.HORSE_STATS
    assert result.question == "Vilken hast har bast vinstprocent?"


def test_intent_classifier_driver_stats():
    """IntentClassifier ska klassificera kusk-fragor som DRIVER_STATS."""
    classifier = IntentClassifier()
    result = classifier.invoke("Vilken kusk vinner mest?")

    assert isinstance(result, IntentClassifierOutput)
    assert result.intent == Intent.DRIVER_STATS


def test_intent_classifier_general():
    """Okand fraga ska ge GENERAL intent."""
    classifier = IntentClassifier()
    result = classifier.invoke("Hur mycket data finns?")

    assert isinstance(result, IntentClassifierOutput)
    assert result.intent == Intent.GENERAL


def test_prompt_builder():
    """PromptBuilder ska bygga en prompt med data-kontext och fraga."""
    builder = PromptBuilder()
    input_data = DataFetcherOutput(
        intent=Intent.HORSE_STATS,
        question="Vilken hast ar bast?",
        params={"name": None},
        data_context="Testdata: 10 starter",
        structured_answer="Basta hasten ar Test med 50% vinst",
    )

    result = builder.invoke(input_data)

    assert isinstance(result, PromptBuilderOutput)
    assert "Testdata: 10 starter" in result.prompt
    assert "Vilken hast ar bast?" in result.prompt
    assert result.structured_answer == "Basta hasten ar Test med 50% vinst"


def test_intent_classifier_upcoming_game():
    """IntentClassifier ska klassificera kommande-spel-fragor som UPCOMING_GAME."""
    classifier = IntentClassifier()
    result = classifier.invoke("Tipsa V86 2026-06-10")

    assert isinstance(result, IntentClassifierOutput)
    assert result.intent == Intent.UPCOMING_GAME
    assert result.params["game_type"] == "V86"
    assert result.params["date"] == "2026-06-10"


def test_intent_classifier_upcoming_without_date():
    """UPCOMING_GAME utan datum ska ge date=None."""
    classifier = IntentClassifier()
    result = classifier.invoke("Tipsa nasta V75")

    assert result.intent == Intent.UPCOMING_GAME
    assert result.params["game_type"] == "V75"
    assert result.params["date"] is None


def test_response_formatter():
    """ResponseFormatter ska returnera ett strukturerat svar med modellnamn."""
    formatter = ResponseFormatter()
    input_data = SmolLMOutput(
        intent=Intent.HORSE_STATS,
        question="Vilken hast ar bast?",
        answer="Elitlansen ar bast med 3 vinster.",
        prompt="...",
        structured_answer="Elitlansen ar bast med 3 vinster.",
    )

    result = formatter.invoke(input_data)

    assert isinstance(result, AiPipelineResponse)
    assert result.question == "Vilken hast ar bast?"
    assert result.intent == "horse_stats"
    assert result.answer == "Elitlansen ar bast med 3 vinster."
    assert result.model == "HuggingFaceTB/SmolLM-135M-Instruct"

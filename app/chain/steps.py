from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from app.chain.runnable import Runnable
from app import db


class Intent(StrEnum):
    HORSE_STATS = "horse_stats"
    DRIVER_STATS = "driver_stats"
    RECENT_STARTS = "recent_starts"
    GENERAL = "general"


INTENT_KEYWORDS: dict[Intent, list[str]] = {
    Intent.HORSE_STATS: ["vinstprocent", "bäst", "basta", "häst", "hast", "statistik"],
    Intent.DRIVER_STATS: ["kusk", "driver", "körsvenn", "tränare"],
    Intent.RECENT_STARTS: ["senaste", "starter", "form", "historik"],
}


# --------------- Pydantic-modeller for kedjans steg ---------------

class IntentClassifierOutput(BaseModel):
    intent: Intent
    question: str
    params: dict[str, str | None]


class DataFetcherOutput(BaseModel):
    intent: Intent
    question: str
    params: dict[str, str | None]
    data_context: str
    structured_answer: str


class PromptBuilderOutput(BaseModel):
    intent: Intent
    question: str
    params: dict[str, str | None]
    data_context: str
    structured_answer: str
    prompt: str


class SmolLMOutput(BaseModel):
    intent: Intent
    question: str
    answer: str
    prompt: str
    structured_answer: str


class AiPipelineResponse(BaseModel):
    question: str
    intent: str
    answer: str
    model: str


# --------------- Kedjesteg ---------------

class IntentClassifier(Runnable):
    """Klassificerar en fraga till en Intent och extraherar eventuellt namn."""

    def invoke(self, data: Any) -> IntentClassifierOutput:
        question: str = data if isinstance(data, str) else data["question"]
        lower = question.lower()

        name = _extract_name(lower)
        intent = Intent.GENERAL
        for key, keywords in INTENT_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                intent = key
                break

        return IntentClassifierOutput(
            intent=intent,
            question=question,
            params={"name": name},
        )


class DataFetcher(Runnable):
    """Hamtar relevant data fran databasen baserat pa intent."""

    def invoke(self, data: IntentClassifierOutput) -> DataFetcherOutput:
        intent = data.intent
        name = data.params.get("name")

        if intent == Intent.HORSE_STATS:
            df = db.load_horse_stats(name)
            if df.empty:
                structured = "Ingen data hittades."
                context = structured
            else:
                top = df.head(10)
                lines = []
                for _, row in top.iterrows():
                    lines.append(
                        f"{row['name']}: {int(row['wins'])}/{int(row['starts'])} vinster "
                        f"({row['win_pct']}%), snittodds {row['avg_odds']:.1f}, "
                        f"snittplacering {row['avg_position']:.1f}"
                    )
                context = df.head(20).to_string(index=False)
                best = top.iloc[0]
                structured = (
                    f"Basta hasten ar {best['name']} med {best['win_pct']}% vinstprocent "
                    f"({int(best['wins'])}/{int(best['starts'])} vinster, "
                    f"snittodds {best['avg_odds']:.1f}).\n\n"
                    f"Topp 10:\n" + "\n".join(lines)
                )

        elif intent == Intent.DRIVER_STATS:
            df = db.load_driver_stats(name)
            if df.empty:
                structured = "Ingen data hittades."
                context = structured
            else:
                top = df.head(10)
                lines = []
                for _, row in top.iterrows():
                    lines.append(
                        f"{row['name']}: {int(row['wins'])}/{int(row['starts'])} vinster "
                        f"({row['win_pct']}%), snittodds {row['avg_odds']:.1f}"
                    )
                context = df.head(20).to_string(index=False)
                best = top.iloc[0]
                structured = (
                    f"Basta kusken ar {best['name']} med {best['win_pct']}% vinstprocent "
                    f"({int(best['wins'])}/{int(best['starts'])} vinster).\n\n"
                    f"Topp 10:\n" + "\n".join(lines)
                )

        elif intent == Intent.RECENT_STARTS:
            if name:
                rows = db.load_recent_starts(name)
                if rows:
                    context = _format_starts(rows)
                    structured = f"Senaste {len(rows)} starter for {name}:\n{context}"
                else:
                    structured = f"Inga starter hittades for {name}."
                    context = structured
            else:
                structured = "Ange ett hastnamn for att se senaste starter."
                context = structured

        else:
            df = db.load_all()
            if df.empty:
                structured = "Databasen ar tom."
                context = structured
            else:
                tracks = ", ".join(df["track"].dropna().unique()[:10])
                structured = (
                    f"Databasen innehaller {len(df)} starter.\n"
                    f"Banor: {tracks}\n"
                    f"Datumintervall: {df['date'].min()} - {df['date'].max()}"
                )
                context = structured

        return DataFetcherOutput(
            intent=data.intent,
            question=data.question,
            params=data.params,
            data_context=context,
            structured_answer=structured,
        )


class PromptBuilder(Runnable):
    """Bygger en prompt fran data-kontext och fraga."""

    template: str = (
        "Du ar en svensk travexpert. Baserat pa foljande data om svensk trav, "
        "svara pa fragan kort och informativt.\n\n"
        "Data:\n{data_context}\n\n"
        "Fraga: {question}\n\n"
        "Svar:"
    )

    def invoke(self, data: DataFetcherOutput) -> PromptBuilderOutput:
        prompt = self.template.format(
            data_context=data.data_context,
            question=data.question,
        )
        return PromptBuilderOutput(
            intent=data.intent,
            question=data.question,
            params=data.params,
            data_context=data.data_context,
            structured_answer=data.structured_answer,
            prompt=prompt,
        )


class SmolLMStep(Runnable):
    """Anropar SmolLM-modellen och returnerar svaret."""

    llm: Any = None

    def invoke(self, data: PromptBuilderOutput) -> SmolLMOutput:
        answer = data.structured_answer
        messages = [{"role": "user", "content": data.prompt}]
        try:
            outputs = self.llm(messages, max_new_tokens=200)
            generated = outputs[0]["generated_text"]
            if isinstance(generated, list):
                llm_answer = generated[-1]["content"]
            else:
                llm_answer = generated[len(data.prompt):].strip()
            if not _is_garbage(llm_answer, data.question):
                answer = llm_answer
        except Exception:
            pass
        return SmolLMOutput(
            intent=data.intent,
            question=data.question,
            answer=answer,
            prompt=data.prompt,
            structured_answer=data.structured_answer,
        )


class ResponseFormatter(Runnable):
    """Formaterar kedjans output till ett strukturerat API-svar."""

    model_name: str = "HuggingFaceTB/SmolLM-135M-Instruct"

    def invoke(self, data: SmolLMOutput) -> AiPipelineResponse:
        return AiPipelineResponse(
            question=data.question,
            intent=data.intent,
            answer=data.answer,
            model=self.model_name,
        )


_ENGLISH_MARKERS = {"the ", "this ", "that ", "with ", "from ", "have ", "here ",
                     "what ", "which ", "there ", "would ", "could ", "should ",
                     "a fun ", "a great ", "a wonderful "}
_CODE_MARKERS = {"```", "def ", "import ", "class ", "function ", "return ", "{}", "[];"}


def _is_garbage(text: str, question: str = "") -> bool:
    if not text or len(text.strip()) < 10:
        return True
    lower = text.lower()
    if sum(1 for m in _CODE_MARKERS if m in lower) >= 2:
        return True
    if question and question.lower() in lower:
        return True
    if sum(1 for m in _ENGLISH_MARKERS if m in lower) >= 2:
        return True
    # Detect repetitive text: split into 4-word chunks and check for repeats
    words = lower.split()
    if len(words) >= 16:
        chunks = [" ".join(words[i:i+4]) for i in range(0, len(words) - 3)]
        if len(set(chunks)) < len(chunks) * 0.5:
            return True
    # Real answers about data should contain numbers
    if not any(c.isdigit() for c in text):
        return True
    return False


def _extract_name(text: str) -> str | None:
    patterns = [
        r"(?:häst|hast|hasten|hästen|kusk|kusken)\s+(\w+)",
        r"(?:om|for|för)\s+(\w+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1)
            if name not in {"den", "en", "ett", "de", "har", "med", "som", "att",
                           "vinner", "ar", "är", "var", "mest", "bast", "bäst"}:
                return name.capitalize()
    return None


def _format_starts(rows: list[dict]) -> str:
    lines = []
    for r in rows[:10]:
        line = (
            f"{r.get('date', '?')} | {r.get('track', '?')} | "
            f"Plats: {r.get('finish_position', '?')} | "
            f"Odds: {r.get('odds', '?')} | "
            f"Tid: {r.get('race_time_sec', '?')}s"
        )
        lines.append(line)
    return "\n".join(lines)

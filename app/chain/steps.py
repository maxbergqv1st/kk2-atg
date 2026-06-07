from __future__ import annotations

import logging
import re
from enum import StrEnum

from pydantic import BaseModel
from transformers import Pipeline

from app.chain.runnable import Runnable
from app import db
from app.services.data_service import UpcomingGameNotFoundError, analyze_upcoming

logger = logging.getLogger(__name__)


class Intent(StrEnum):
    HORSE_STATS = "horse_stats"
    DRIVER_STATS = "driver_stats"
    RECENT_STARTS = "recent_starts"
    UPCOMING_GAME = "upcoming_game"
    GENERAL = "general"


INTENT_KEYWORDS: dict[Intent, list[str]] = {
    Intent.UPCOMING_GAME: ["kommande", "upcoming", "nästa", "nasta", "tipsa", "speltips", "betta", "bet", "v86", "v85", "v75", "v64"],
    Intent.HORSE_STATS: ["vinstprocent", "bäst", "basta", "häst", "hast", "statistik"],
    Intent.DRIVER_STATS: ["kusk", "driver", "körsven", "tränare"],
    Intent.RECENT_STARTS: ["senaste", "starter", "form", "historik"],
}


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


class IntentClassifier(Runnable[str, IntentClassifierOutput]):
    """Klassificerar en fraga till en Intent och extraherar eventuellt namn."""

    def invoke(self, data: str) -> IntentClassifierOutput:
        question = data
        lower = question.lower()

        name = _extract_name(lower)
        intent = Intent.GENERAL
        for key, keywords in INTENT_KEYWORDS.items():
            if any(kw in lower for kw in keywords):
                intent = key
                break

        params: dict[str, str | None] = {"name": name}
        if intent == Intent.UPCOMING_GAME:
            params["game_type"] = _extract_game_type(lower)
            params["date"] = _extract_date(lower)

        logger.info("Intent: %s (fraga: %s)", intent, question[:80])
        return IntentClassifierOutput(
            intent=intent,
            question=question,
            params=params,
        )


class DataFetcher(Runnable[IntentClassifierOutput, DataFetcherOutput]):
    """Hamtar relevant data fran databasen baserat pa intent."""

    def invoke(self, data: IntentClassifierOutput) -> DataFetcherOutput:
        intent = data.intent
        name = data.params.get("name")

        if intent == Intent.HORSE_STATS:
            horse_ids = None
            if name:
                hid = db.lookup_horse_id(name)
                horse_ids = [hid] if hid else []
            stats = db.load_horse_stats(horse_ids)
            if not stats:
                structured = "Ingen data hittades."
                context = structured
            else:
                ranked = list(stats.values())[:10]
                lines = []
                for s in ranked:
                    lines.append(
                        f"{s['name']}: {s['wins']}/{s['starts']} vinster "
                        f"({s['win_pct']}%), snittodds {s['avg_odds']:.1f}, "
                        f"snittplacering {s['avg_position']:.1f}"
                    )
                context = "\n".join(lines)
                best = ranked[0]
                structured = (
                    f"Basta hasten ar {best['name']} med {best['win_pct']}% vinstprocent "
                    f"({best['wins']}/{best['starts']} vinster, "
                    f"snittodds {best['avg_odds']:.1f}).\n\n"
                    f"Topp 10:\n" + "\n".join(lines)
                )

        elif intent == Intent.DRIVER_STATS:
            driver_ids = None
            if name:
                did = db.lookup_driver_id(name)
                driver_ids = [did] if did else []
            stats = db.load_driver_stats(driver_ids)
            if not stats:
                structured = "Ingen data hittades."
                context = structured
            else:
                ranked = list(stats.values())[:10]
                lines = []
                for s in ranked:
                    lines.append(
                        f"{s['driver_name']}: {s['wins']}/{s['starts']} vinster "
                        f"({s['win_pct']}%)"
                    )
                context = "\n".join(lines)
                best = ranked[0]
                structured = (
                    f"Basta kusken ar {best['driver_name']} med {best['win_pct']}% vinstprocent "
                    f"({best['wins']}/{best['starts']} vinster).\n\n"
                    f"Topp 10:\n" + "\n".join(lines)
                )

        elif intent == Intent.RECENT_STARTS:
            if name:
                hid = db.lookup_horse_id(name)
                rows = db.load_recent_starts(hid) if hid else []
                if rows:
                    context = _format_starts(rows)
                    structured = f"Senaste {len(rows)} starter for {name}:\n{context}"
                else:
                    structured = f"Inga starter hittades for {name}."
                    context = structured
            else:
                structured = "Ange ett hastnamn for att se senaste starter."
                context = structured

        elif intent == Intent.UPCOMING_GAME:
            game_type = data.params.get("game_type") or "V86"
            date_str = data.params.get("date") or "2026-06-10"
            try:
                game = analyze_upcoming(game_type, date_str)
            except Exception:
                structured = f"Inget {game_type}-spel hittades for {date_str}."
                context = structured
            else:
                structured, context = _format_upcoming(game)

        else:
            count = db.count_starters()
            if count == 0:
                structured = "Databasen ar tom."
                context = structured
            else:
                dates = db.stored_dates()
                structured = (
                    f"Databasen innehaller {count} starter.\n"
                    f"Datumintervall: {dates[0]} - {dates[-1]}"
                )
                context = structured

        return DataFetcherOutput(
            intent=data.intent,
            question=data.question,
            params=data.params,
            data_context=context,
            structured_answer=structured,
        )


class PromptBuilder(Runnable[DataFetcherOutput, PromptBuilderOutput]):
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


class SmolLMStep(Runnable[PromptBuilderOutput, SmolLMOutput]):
    """Anropar SmolLM-modellen och returnerar svaret."""

    llm: Pipeline = None

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
            else:
                logger.warning("LLM-svar filtrerat som garbage, anvander structured fallback")
        except Exception as e:
            logger.error("SmolLM-fel: %s", e)
        return SmolLMOutput(
            intent=data.intent,
            question=data.question,
            answer=answer,
            prompt=data.prompt,
            structured_answer=data.structured_answer,
        )


class ResponseFormatter(Runnable[SmolLMOutput, AiPipelineResponse]):
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
    # Reject text with too few real words (mostly numbers/fragments)
    alpha_words = [w for w in words if len(w) >= 3 and w.isalpha()]
    if len(words) > 5 and len(alpha_words) / len(words) < 0.25:
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


def _extract_game_type(text: str) -> str:
    for gt in ["v86", "v85", "v75", "v64"]:
        if gt in text:
            return gt.upper()
    return "V86"


def _extract_date(text: str) -> str | None:
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else None


def _format_upcoming(game) -> tuple[str, str]:
    """Tar en UpcomingGameResponse och returnerar (structured_answer, context)."""
    summary_lines: list[str] = []
    context_lines: list[str] = []
    best_bets: list[dict] = []

    for race in game.races:
        track_name = race.track or "?"
        dist = race.distance_m or "?"

        scored: list[dict] = []
        for s in race.starters:
            wp = s.overall.win_pct if s.overall else 0
            tp = s.track.win_pct if s.track else 0
            dp = s.driver.win_pct if s.driver else 0
            starts = s.overall.starts if s.overall else 0
            score = wp * 0.5 + tp * 0.3 + dp * 0.2
            scored.append({"name": s.horse_name, "pos": s.post_position,
                           "driver": s.driver_name, "wp": wp, "tp": tp,
                           "dp": dp, "score": score, "starts": starts,
                           "race": race.race_number, "track": track_name, "dist": dist})

        ranked = sorted(scored, key=lambda x: x["score"], reverse=True)

        if ranked and ranked[0]["starts"] >= 1:
            best_bets.append(ranked[0])

        summary_lines.append(f"Lopp {race.race_number} - {track_name} ({dist}m):")
        for i, e in enumerate(ranked[:3], 1):
            wp_s = f"{e['wp']:.1f}%" if e["starts"] else "okand"
            bana = f", bana {e['tp']:.1f}%" if e["tp"] else ""
            summary_lines.append(
                f"  {i}. {e['name']} (spar {e['pos']}) "
                f"- {wp_s} vinst{bana} ({e['starts']} starter)")
        summary_lines.append("")

        context_lines.append(f"Lopp {race.race_number} - {track_name} ({dist}m):")
        for i, e in enumerate(ranked, 1):
            wp_s = f"{e['wp']:.1f}%" if e["starts"] else "?"
            tp_s = f"{e['tp']:.1f}%" if e["tp"] else "-"
            context_lines.append(
                f"  {i}. {e['name']} (spar {e['pos']}) "
                f"vinst: {wp_s} | bana: {tp_s} | kusk: {e['dp']:.1f}% "
                f"({e['starts']} starter)")

    best_sorted = sorted(best_bets, key=lambda x: x["score"], reverse=True)
    best_lines: list[str] = [f"BASTA BETS ({game.game_type} {game.date}):"]
    for e in best_sorted[:5]:
        bana = f", bana {e['tp']:.1f}%" if e["tp"] else ""
        best_lines.append(
            f"  Lopp {e['race']}: {e['name']} (spar {e['pos']}) "
            f"- {e['wp']:.1f}% vinst{bana}, kusk {e['dp']:.1f}% "
            f"({e['starts']} starter)")

    structured = "\n".join(best_lines) + "\n\n" + "\n".join(summary_lines)
    context = "\n".join(context_lines)
    return structured, context


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

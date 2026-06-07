# kk2-atg

Datapipeline och AI-analys för svensk trav (ATG). Hämtar alla starter från v64, v75, v85, v86 från ATG:s egna API, lagrar i SQLite databas och erbjuder AI-drivna insikter via SmolLM.

Rekommenderar att hämta minst 1000 dagar / helst så många dagar som det går. Detta för att få en stor mängd data att jämföra framtida spel mot. (1000 dagar kan ta 10-30 minuter.)

## Kom igang

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Servern startar på `http://127.0.0.1:8000` frontend. Swagger-docs finns på `/docs`.

## API-endpoints

### Health

```bash
# Kontrollera servern
curl http://127.0.0.1:8000/health
```

### Data

```bash
# Hämta data till databasen ATG.db / ändra days, för att hämta fler datums starter.
curl -X POST http://127.0.0.1:8000/data/fetch \
  -H "Content-Type: application/json" \
  -d '{"days": 3, "dataset": "starters"}'

# Hämta häststatistik istället.
curl -X POST http://127.0.0.1:8000/data/fetch \
  -H "Content-Type: application/json" \
  -d '{"days": 5, "dataset": "horses"}'

# Antal starter i databasen, ett datum har flera starter.
curl http://127.0.0.1:8000/data/count

# Vilka datum som finns lagrade
curl http://127.0.0.1:8000/data/dates

# Lista starter (default 50, kan andras med ?limit=)
curl http://127.0.0.1:8000/data/starters
curl http://127.0.0.1:8000/data/starters?limit=10

# Statistik (describe) over all data
curl http://127.0.0.1:8000/data/stats

# Förhandsgranska data (default 10 rader)
curl http://127.0.0.1:8000/data/preview
curl http://127.0.0.1:8000/data/preview?n=5
```

### AI
Ställ frågor om travdata på ett naturligt sätt. SmolLM 135M instruct används för att formulera svar baserat på databasinnehållet.

```bash
# Vilken häst har bäst vinstprocent?
curl -X POST http://127.0.0.1:8000/ai/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Vilken hast har bast vinstprocent?"}'

# Kuskstatistik
curl -X POST http://127.0.0.1:8000/ai/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Vilken kusk vinner mest?"}'

# Senaste starter för en specifik häst
curl -X POST http://127.0.0.1:8000/ai/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Visa senaste starter for Elitlansen"}'

# Översikt över databasen
curl -X POST http://127.0.0.1:8000/ai/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hur mycket data finns?"}'
```

AI-endpointet tolkar frågan automatiskt och hämtar relevant data:

| Intent | Triggerord | Beskrivning |
|--------|-----------|-------------|
| `horse_stats` | häst, vinstprocent, bäst, statistik | Statistik per häst |
| `driver_stats` | kusk, driver, tränare | Statistik per kusk |
| `recent_starts` | senaste, starter, form, historik | En hästs senaste lopp |
| `general` | (övriga frågor) | Översikt över databasen |

## Teknikstack

- **Python 3.14+** med **uv** 
- **FastAPI** + **Uvicorn**
- **SQLAlchemy** + **SQLite**
- **Pandas** / **NumPy** 
- **HuggingFace Transformers** + **PyTorch**  (SmolLM)

## Projektstruktur

```
app/
  main.py              # FastAPI-app, lifespan, router-registrering
  atg.py               # ATG API-klient, hämtar loppdata
  api/
    health.py          # GET /health
    data.py            # Data-endpoints (fetch, count, dates, starters, stats, preview)
    ai.py              # POST /ai/ask
  chain/
    runnable.py        # Composable Runnable-basklasser (pipe-operator)
    steps.py           # IntentClassifier, DataFetcher, PromptBuilder, SmolLMStep
    pipeline.py        # Bygger och cachar AI-pipelinen
  db/
    schema.py          # SQLAlchemy-modell (Starter-tabell)
    operations.py      # CRUD + aggregeringsfragor
  models/
    models.py          # Pydantic request/response-scheman
  services/
    data_service.py    # Orkestrerar ATG-hamtning och databaslagring
    ai_service.py      # Tunnt lager over AI-pipelinen
```

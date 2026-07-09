# a2ui_starter

A runnable starter for building **A2UI**-emitting ADK agents that render as
rich, Google-brand-styled widgets on any A2UI renderer — including the
built-in renderer inside **Gemini Enterprise**.

The 10 rich widgets in `app/widgets/` are all **compositions of
the A2UI Basic Catalog primitives** (`Text`, `Row`, `Column`, `Card`, `List`,
`Button`, `Icon`, `Divider`). The A2UI Basic Catalog does not itself define
`DataTable`, `TagChip`, `CitationSource`, etc. — but any conforming renderer
can render them because they resolve to primitives.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [agents-cli](https://pypi.org/project/google-agents-cli/) (`uv tool install google-agents-cli`)
- Google Cloud credentials (`gcloud auth application-default login`)

## Quickstart

```bash
# Copy and configure environment
cp .env-template .env
# Edit .env with your GOOGLE_CLOUD_PROJECT

# Install dependencies
make install          # or: agents-cli install

# Run tests
make test             # or: uv run pytest tests/ -q

# Interactive playground (agents-cli)
make playground       # or: agents-cli playground

# Widget preview harness
make preview          # or: uv run uvicorn app.preview.server:app --reload --port 8080
```

Open <http://localhost:8080/preview> to see all 10 widgets rendered against
`GET /api/demo`, which returns a full A2UI stream (`createSurface` +
`updateDataModel`) built from `sample_data.py`.

## Project structure

```
a2ui_starter/
├── app/                          # Agent package (agents-cli convention)
│   ├── __init__.py               # Exports ADK App
│   ├── agent.py                  # ADK Agent + A2UI schema manager
│   ├── agent_runtime_app.py      # Agent Engine deployment entrypoint
│   ├── a2ui.py                   # A2UI envelope builders
│   ├── sample_data.py            # Demo widget instances
│   ├── widgets/                  # 10 composed rich widgets
│   ├── preview/                  # FastAPI preview harness
│   └── app_utils/                # A2UI callbacks, telemetry, typing
├── tests/                        # pytest test suite
├── agents-cli-manifest.yaml      # agents-cli project metadata
├── GEMINI.md                     # Coding agent guidance
├── pyproject.toml                # uv/hatch project config
├── .env-template                 # Environment template
└── Makefile                      # Common dev commands
```

## ADK integration

`app/agent.py` uses the full ADK stack:

- **`Agent`** from `google.adk.agents` with `Gemini` model
- **`A2uiSchemaManager`** from `a2ui-agent-sdk` for system prompt generation
- **`before_model_callback`** strips echoed A2UI blobs from conversation history
- **`after_model_callback`** (`a2ui_callback`) extracts A2UI JSON from model output
  and wraps it as inline-data blobs for the ADK web client
- **`render_widgets`** tool: the model emits a structured description of which
  widgets to render; the tool builds Pydantic `Widget` instances and emits
  A2UI streams

## Version pinning (Gemini Enterprise)

Gemini Enterprise's built-in renderer is pinned to **A2UI v0.8**. This repo
therefore emits `{"version": "v0.8", ...}` envelopes by default
(`A2UI_BASIC_CATALOG_ID` in `a2ui.py` points at the v0.8 catalog). When
GE's renderer catches up to v0.9 / v1.0, only that constant needs to
change — the widget layer is unaffected because it produces the same
`components` adjacency lists.

## Development commands

| Command | Purpose |
|---------|---------|
| `make install` | Install dependencies via agents-cli |
| `make test` | Run pytest test suite |
| `make preview` | Widget preview harness on port 8080 |
| `make playground` | Interactive ADK playground |
| `make deploy` | Deploy to Agent Engine |
| `make lint` | Run code quality checks |

## Deployment

```bash
# Deploy to Agent Engine
agents-cli deploy

# Or manually via Vertex AI
# vertexai.Client(...).agent_engines.create(agent_engine=agent, ...)
```

## Whitepaper

See the accompanying whitepaper on A2UI on Gemini Enterprise for the full
architectural rationale, catalog-composition patterns, and deployment
recipes across Agent Engine / Cloud Run / GKE.

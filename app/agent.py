"""ADK Agent that emits A2UI v1.0 rich widgets for Gemini Enterprise.

Uses ``google-adk`` + ``a2ui-agent-sdk``'s ``SendA2uiToClientToolset``
to give the model a proper ``send_a2ui_json_to_client`` tool.  The SDK
validates A2UI JSON and the Gemini Enterprise renderer handles v1.0
natively — no blob injection callbacks needed.
"""

from __future__ import annotations

import builtins
import json
import logging
import os
from pathlib import Path
from typing import Any

import google.auth
import vertexai
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.parser.payload_fixer import parse_and_fix
from a2ui.schema.common_modifiers import remove_strict_validation
from a2ui.schema.constants import VERSION_0_9_1
from a2ui.schema.manager import A2uiSchemaManager
from google.adk import models as _adk_models
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini

from .a2ui import widget_to_a2ui_stream
from .sample_data import build_all_widgets

# Ensure builtins.models exists for a2ui SDK compatibility
if not hasattr(builtins, "models"):
    builtins.models = _adk_models

from a2ui.adk.send_a2ui_to_client_toolset import SendA2uiToClientToolset  # noqa: E402

logger = logging.getLogger(__name__)

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
vertexai.init(project=project_id, location="global")

_APP_DIR = Path(__file__).parent
EXAMPLES_DIR = _APP_DIR / "examples"

# --------------------------------------------------------------------------- #
# A2UI examples — loaded from JSON files
# --------------------------------------------------------------------------- #

def _load_examples() -> str:
    """Load all example JSON files into a labeled prompt block."""
    examples_text = ""
    for json_file in sorted(EXAMPLES_DIR.glob("*.json")):
        label = json_file.stem.upper().replace("_", " ")
        try:
            content = json_file.read_text()
            # Validate it's actual JSON
            json.loads(content)
            examples_text += f"\n---BEGIN {label} EXAMPLE---\n{content}\n---END {label} EXAMPLE---\n"
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load example %s: %s", json_file, e)
    return examples_text


A2UI_EXAMPLES = _load_examples()


def run_demo() -> list[dict]:
    """Fabricate a demo A2UI stream from ``sample_data`` widgets.

    Used by the preview harness at ``GET /api/demo``.
    """

    stream: list[dict] = []
    for widget in build_all_widgets():
        surface_id = f"surface_{widget.id}"
        stream.extend(widget_to_a2ui_stream(surface_id, widget))
    return stream


# --------------------------------------------------------------------------- #
# Lenient A2UI toolset (handles model JSON quirks)
# --------------------------------------------------------------------------- #


def _parse_concatenated_json_values(payload: str) -> list[Any]:
    decoder = json.JSONDecoder()
    text = (
        payload.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .strip()
    )
    values: list[Any] = []
    idx = 0
    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break
        value, idx = decoder.raw_decode(text, idx)
        values.append(value)
    return values if len(values) > 1 else []


def _parse_lenient_a2ui_payload(payload: str) -> list[dict[str, Any]]:
    """Parse A2UI JSON, accepting accidentally concatenated top-level values."""
    try:
        return parse_and_fix(payload)
    except Exception as original_error:
        try:
            values = _parse_concatenated_json_values(payload)
        except Exception as recovery_error:
            raise original_error from recovery_error
        if not values:
            raise original_error from None

        messages: list[dict[str, Any]] = []
        for value in values:
            if isinstance(value, list):
                messages.extend(value)
            elif isinstance(value, dict):
                messages.append(value)
            else:
                raise original_error from None

        if not all(isinstance(message, dict) for message in messages):
            raise original_error from None
        logger.warning(
            "Recovered A2UI payload with %d concatenated top-level JSON values",
            len(values),
        )
        return messages


class LenientSendA2uiToClientToolset(SendA2uiToClientToolset):
    """A2UI toolset that avoids slow LLM retry loops for recoverable JSON errors."""

    def __init__(self, a2ui_enabled, a2ui_catalog, a2ui_examples):
        super().__init__(a2ui_enabled, a2ui_catalog, a2ui_examples)
        self._ui_tools = [
            self._LenientSendA2uiJsonToClientTool(a2ui_catalog, a2ui_examples)
        ]

    class _LenientSendA2uiJsonToClientTool(
        SendA2uiToClientToolset._SendA2uiJsonToClientTool
    ):
        async def run_async(self, *, args: dict[str, Any], tool_context) -> Any:
            try:
                a2ui_json = args.get(self.A2UI_JSON_ARG_NAME)
                if not a2ui_json:
                    raise ValueError(
                        f"Failed to call tool {self.TOOL_NAME} because missing "
                        f"required arg {self.A2UI_JSON_ARG_NAME}"
                    )

                a2ui_catalog = await self._resolve_a2ui_catalog(tool_context)
                a2ui_json_payload = _parse_lenient_a2ui_payload(a2ui_json)
                a2ui_catalog.validator.validate(a2ui_json_payload)

                # Skip summarization — the SDK / Gemini Enterprise handles
                # blob injection natively for validated A2UI payloads.
                tool_context.actions.skip_summarization = True
                return {self.VALIDATED_A2UI_JSON_KEY: a2ui_json_payload}

            except Exception as e:
                err = f"Failed to call A2UI tool {self.TOOL_NAME}: {e}"
                logger.error(err)
                return {self.TOOL_ERROR_KEY: err}



# --------------------------------------------------------------------------- #
# Schema Manager + System Prompt
# --------------------------------------------------------------------------- #

# Use v0.9.1 catalog (v1.0 uses same components with flat format)
schema_manager = A2uiSchemaManager(
    version=VERSION_0_9_1,
    catalogs=[
        BasicCatalog.get_config(
            version=VERSION_0_9_1,
            examples_path=str(EXAMPLES_DIR),
        ),
    ],
    schema_modifiers=[remove_strict_validation],
)

ROLE_DESCRIPTION = """\
You are a helpful Google Cloud assistant that renders rich, interactive A2UI \
widgets. If the `send_a2ui_json_to_client` tool is available to you, you MUST \
use it with the `a2ui_json` argument to send A2UI JSON payloads to the client \
for rendering rich UI. If it is NOT in your available tools list, respond with \
helpful plain text instead.

**CRITICAL — when using `send_a2ui_json_to_client`, FOLLOW THESE RULES:**
1. Use the native function calling interface. Do NOT generate code.
2. Pass `a2ui_json` as a single compact JSON string.
3. Do NOT use `True`/`False` (Python). Use `true`/`false` (JSON).
4. **JSON syntax MUST be strictly valid.** No trailing commas. Escape quotes.
5. The whole `a2ui_json` argument is a JSON ARRAY of A2UI messages.
6. **Exactly ONE top-level JSON value.** Starts with `[`, ends with `]`.
7. **One tool call per response.**
8. **Always emit a short plain-text intro alongside the tool call.**
"""

WORKFLOW_DESCRIPTION = """\
1.  **Analyze the Request:** Determine the user's intent.
    * "Show me some widgets" -> **Intent:** Rich Widget Demo.
    * "Show X on the map" -> **Intent:** Map View.
    * "Get directions from A to B" -> **Intent:** Directions.

2.  **Select Example:** Based on the intent, choose the correct example.
    * **Rich Widget Demo** -> Use `---BEGIN RICH WIDGETS EXAMPLE---`.
    * **Map View** -> Use `---BEGIN MAP EXAMPLE---`.
    * **Directions** -> Use `---BEGIN DIRECTIONS EXAMPLE---`.

3.  **Construct the JSON Payload:**
    * Use the chosen example as the base for the `a2ui_json` argument.
    * **Generate a new `surfaceId`** for each request.
    * For maps: Use an Image component with Google Maps Static API URL.
    * For all surfaces: Every component tree MUST have a component with id `root`.

4.  **Call the Tool:** Call `send_a2ui_json_to_client` with the payload.
"""

UI_DESCRIPTION = """\
**Available Components (v0.9.1 flat format):**
- **Text**: `{"id":"my-id","component":"Text","text":"Hello","variant":"h2"}`
- **Image**: `{"id":"my-id","component":"Image","url":"https://...","fit":"cover","altText":"description"}`
- **Icon**: `{"id":"my-id","component":"Icon","name":"check_circle"}`
- **Row/Column**: Layout containers. `{"id":"row1","component":"Row","children":["id1","id2"]}`
- **Card**: Container. `{"id":"card1","component":"Card","child":"child-id"}`
- **Divider**: Visual separator. `{"id":"div1","component":"Divider"}`
- **Button**: `{"id":"btn1","component":"Button","child":"label-id"}`
- **Tabs**: `{"id":"tabs1","component":"Tabs","tabs":[{"label":"Tab 1","child":"content-id1"}]}`
- **List**: `{"id":"list1","component":"List","items":["item-id1","item-id2"]}`
- **Slider**: `{"id":"s1","component":"Slider","min":0,"max":100,"value":50}`
- **CheckBox**: `{"id":"cb1","component":"CheckBox","label":"Accept","value":true}`
- **TextField**: `{"id":"tf1","component":"TextField","label":"Name","value":""}`
- **AudioPlayer**: `{"id":"ap1","component":"AudioPlayer","url":"https://..."}`
- **Video**: `{"id":"v1","component":"Video","url":"https://..."}`

**v0.9.1 Flat Format Rules:**
- Properties are FLAT on the component object (NOT nested inside a type wrapper).
- String values are plain strings (NOT `{"literalString":"value"}`).
- `children` is a plain array of string IDs (NOT `{"explicitList":[...]}`).
- `child` is a plain string component ID.
- Component type is the `component` field value: `"component":"Text"`.

**Envelope Format:**
1. `createSurface`: `{"version":"v0.9","createSurface":{"surfaceId":"my-surface","catalogId":"https://a2ui.org/specification/v0_9/basic_catalog.json"}}`
2. `updateComponents`: `{"version":"v0.9","updateComponents":{"surfaceId":"my-surface","components":[...]}}`

**Layout Rules:**
- Every surface MUST have a component with `id: "root"`.
- Use `Column` as the root layout for vertical stacking.
- Use `Row` for horizontal arrangement.

**CRITICAL:** Do NOT use chart/graph/sparkline components — they don't exist. \
Use tabular layouts (Text in Row/Column) for data visualization.
"""

_raw_instruction = schema_manager.generate_system_prompt(
    role_description=ROLE_DESCRIPTION,
    workflow_description=WORKFLOW_DESCRIPTION,
    ui_description=UI_DESCRIPTION,
    include_schema=True,
    include_examples=True,
)

# ADK's instructions_utils treats {word} as session-state template variables.
# It strips ALL leading '{' and trailing '}' from matches, so doubling braces
# doesn't help ({{expression}} → 'expression' → KeyError).
# Replace bare {identifier} patterns with angle-bracket notation instead.
import re as _re

instruction = _re.sub(
    r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}',
    r'<\1>',
    _raw_instruction,
)


# --------------------------------------------------------------------------- #
# Agent + App
# --------------------------------------------------------------------------- #

root_agent = Agent(
    model=Gemini(
        model="gemini-3.5-flash",
        client_kwargs={
            "location": "global",
            "vertexai": True,
            "project": project_id,
        },
    ),
    name="a2ui_demo_agent",
    description=(
        "A Google Cloud assistant that renders rich, structured A2UI widgets "
        "including tables, metrics, maps, timelines, callouts, and more."
    ),
    instruction=instruction,
    generate_content_config={"temperature": 1.0},
    tools=[
        LenientSendA2uiToClientToolset(
            a2ui_enabled=lambda ctx: ctx.state.get(
                "system:a2ui_enabled", True
            ),
            a2ui_catalog=lambda ctx: ctx.state.get(
                "system:a2ui_catalog",
                schema_manager.get_selected_catalog(),
            ),
            a2ui_examples=lambda ctx: ctx.state.get(
                "system:a2ui_examples", A2UI_EXAMPLES
            ),
        ),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)

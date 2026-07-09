"""ADK Agent that emits A2UI rich widgets via the SDK toolset.

Uses ``google-adk`` + ``a2ui-agent-sdk``'s ``SendA2uiToClientToolset``
to give the model a proper ``send_a2ui_json_to_client`` tool. The SDK
validates A2UI JSON and injects blobs correctly — no more fragile
text-parsing callbacks.
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
from a2ui.schema.constants import VERSION_0_8
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
# (Custom catalog provider removed — v0.8 uses only BasicCatalog)
# --------------------------------------------------------------------------- #


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

                # Stash validated messages for the after_model_callback to
                # inject as blobs when the model generates its summary.
                tool_context.state[_A2UI_PENDING_KEY] = a2ui_json_payload

                # Do NOT skip summarization — the model needs a second call
                # so after_model_callback can fire and inject blobs.
                return {"result": "A2UI components rendered successfully."}

            except Exception as e:
                err = f"Failed to call A2UI tool {self.TOOL_NAME}: {e}"
                logger.error(err)
                return {self.TOOL_ERROR_KEY: err}



# --------------------------------------------------------------------------- #
# Schema Manager + System Prompt
# --------------------------------------------------------------------------- #

schema_manager = A2uiSchemaManager(
    version=VERSION_0_8,
    catalogs=[
        BasicCatalog.get_config(
            version=VERSION_0_8,
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
    * **Map View** -> Use `---BEGIN MAP EXAMPLE---`. Use the `WebFrameUrl` \
component with URL `/maps/embed?mode=place&q=URL_ENCODED_QUERY`.
    * **Directions** -> Use `---BEGIN DIRECTIONS EXAMPLE---`. Use `WebFrameUrl` \
with URL `/maps/embed?mode=directions&origin=URL_ENCODED_ORIGIN&destination=URL_ENCODED_DESTINATION`.

3.  **Construct the JSON Payload:**
    * Use the chosen example as the base for the `a2ui_json` argument.
    * **Generate a new `surfaceId`** for each request.
    * For maps: The URL must NOT include any API key.
    * For all surfaces: Every component tree MUST have a component with id `root`.

4.  **Call the Tool:** Call `send_a2ui_json_to_client` with the payload.
"""

UI_DESCRIPTION = """\
**Available Components (v0.8):**
- **Text**: `{"component":{"Text":{"text":{"literalString":"Hello"},"usageHint":"h2"}}}`
- **Image**: `{"component":{"Image":{"url":{"literalString":"https://..."},"fit":"cover"}}}`
- **Icon**: `{"component":{"Icon":{"name":{"literalString":"check_circle"}}}}`
- **Row/Column**: Layout containers. `children: {"explicitList":["id1","id2"]}`.
- **Card**: Container. `{"component":{"Card":{"child":"child-id"}}}`.
- **Divider**: Visual separator. `{"component":{"Divider":{}}}`.
- **Button**: `{"component":{"Button":{"child":"label-id"}}}`.

**v0.8 Key Rules:**
- String properties use `{"literalString": "value"}` wrappers.
- Component type is a DYNAMIC KEY inside `"component"`: `{"component":{"Text":{...}}}`.
- `children` uses `{"explicitList": ["id1","id2"]}` (NOT a bare array).
- `child` is a plain string component ID.

**Envelope Format:**
1. `beginRendering`: `{"beginRendering":{"surfaceId":"my-surface","root":"root"}}`
2. `surfaceUpdate`: `{"surfaceUpdate":{"surfaceId":"my-surface","components":[...]}}`
3. `dataModelUpdate`: `{"dataModelUpdate":{"surfaceId":"my-surface","dataModel":{...}}}`

**Google Maps Integration:**
- For maps, use an Image component or plain text with a link — iframes are not \
supported in v0.8.
- Alternatively describe map details textually.

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
# Callbacks for ADK playground rendering
# --------------------------------------------------------------------------- #

_A2UI_BLOB_MARKER = b"<a2a_datapart_json>"
_A2UI_PENDING_KEY = "temp:a2ui_pending"


def _wrap_a2ui_part(a2ui_message: dict) -> Any:
    """Wrap an A2UI message dict as an inline-data blob for the ADK dev-UI."""
    import json as _json
    from google.genai import types

    datapart_json = _json.dumps({
        "kind": "data",
        "metadata": {"mimeType": "application/json+a2ui"},
        "data": a2ui_message,
    })
    blob_data = (
        _A2UI_BLOB_MARKER
        + datapart_json.encode("utf-8")
        + b"</a2a_datapart_json>"
    )
    return types.Part(
        inline_data=types.Blob(data=blob_data, mime_type="text/plain")
    )


def _after_model_callback(callback_context, llm_response):
    """Inject A2UI blobs from stashed tool responses into the model output.

    After the model summarizes the tool call, this callback appends the
    validated A2UI messages as inline-data blobs the ADK dev-UI can render.
    """
    from google.adk.models.llm_response import LlmResponse
    from google.genai import types

    pending = callback_context.state.get(_A2UI_PENDING_KEY)
    if not pending:
        return None

    # Clear the pending state
    callback_context.state[_A2UI_PENDING_KEY] = None

    logger.info("after_model_callback: injecting %d A2UI blob(s)", len(pending))

    # Build blob parts from the stashed messages
    blob_parts = [_wrap_a2ui_part(msg) for msg in pending]

    # Keep any text parts from the model's summary and add blobs
    existing_parts = []
    if llm_response and llm_response.content and llm_response.content.parts:
        existing_parts = list(llm_response.content.parts)

    all_parts = existing_parts + blob_parts

    return LlmResponse(
        content=types.Content(role="model", parts=all_parts),
        custom_metadata={"a2a:response": True},
    )


def _before_model_callback(callback_context, llm_request):
    """Strip echoed A2UI blobs from history so the model doesn't regurgitate."""
    from google.genai import types

    if not llm_request.contents:
        return None

    for content in llm_request.contents:
        if not content.parts:
            continue
        clean_parts = [
            types.Part(text="[A2UI component rendered]")
            if (
                p.inline_data
                and p.inline_data.mime_type == "text/plain"
                and _A2UI_BLOB_MARKER in (p.inline_data.data or b"")
            )
            else p
            for p in content.parts
        ]
        content.parts[:] = clean_parts

    return None


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
            a2ui_enabled=True,
            a2ui_catalog=schema_manager.get_selected_catalog(),
            a2ui_examples=A2UI_EXAMPLES,
        ),
    ],
    before_model_callback=_before_model_callback,
    after_model_callback=_after_model_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)



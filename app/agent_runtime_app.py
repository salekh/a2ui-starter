# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Agent Runtime entry point with A2UI event conversion for Gemini Enterprise.

The default ``AdkApp`` serializes ADK events directly — the tool result
``{validated_a2ui_json: [...]}`` ends up as text.  Gemini Enterprise needs
it as an ``inline_data`` blob with ``application/a2ui+json`` MIME type.

This module overrides ``streaming_agent_run_with_events`` to intercept
ADK events and perform the conversion, along with maps proxy URL
rewriting and catalog ID repair from the reference implementation.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
from typing import Any
from urllib.parse import parse_qs, urlencode

import vertexai
from dotenv import load_dotenv
from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
from google.cloud import logging as google_cloud_logging
from vertexai.agent_engines.templates.adk import AdkApp

from app.agent import app as adk_app
from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback

# Load environment variables from .env file at runtime
load_dotenv()

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

A2UI_MIME_TYPE = "application/json+a2ui"
VALIDATED_A2UI_JSON_KEY = "validated_a2ui_json"
TOOL_NAME = "send_a2ui_json_to_client"

# A2UI message types that must each travel as their own message.
_A2UI_UPDATE_TYPES = (
    "createSurface", "deleteSurface", "updateDataModel", "updateComponents",
)

# Matches the /maps/embed proxy URL produced by the LLM.
_MAPS_PROXY_RE = re.compile(r"^/maps/embed\?(.+)$")


# --------------------------------------------------------------------------- #
# Maps proxy URL rewriting
# --------------------------------------------------------------------------- #

def _get_google_maps_api_key() -> str | None:
    return os.environ.get("GOOGLE_MAPS_API_KEY")


def _proxy_url_to_full_embed_url(url: str) -> str:
    """Convert /maps/embed?mode=place&q=... to a full Google Maps Embed URL."""
    match = _MAPS_PROXY_RE.match(url)
    if not match:
        return url
    api_key = _get_google_maps_api_key()
    if not api_key:
        return url
    params = parse_qs(match.group(1), keep_blank_values=True)
    mode = params.pop("mode", ["place"])[0]
    flat_params = {k: v[0] for k, v in params.items()}
    qs = urlencode(flat_params)
    return f"https://www.google.com/maps/embed/v1/{mode}?key={api_key}&{qs}"


def _replace_proxy_urls(obj: Any) -> Any:
    """Recursively walk A2UI data and replace /maps/embed proxy URLs."""
    if isinstance(obj, str):
        return _proxy_url_to_full_embed_url(obj)
    if isinstance(obj, dict):
        return {k: _replace_proxy_urls(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_proxy_urls(item) for item in obj]
    return obj


# --------------------------------------------------------------------------- #
# A2UI message splitting and catalog repair
# --------------------------------------------------------------------------- #

def _split_combined_a2ui_data(data: dict) -> list[dict]:
    """Split one A2UI message containing multiple update types into separate messages."""
    types_present = [t for t in _A2UI_UPDATE_TYPES if t in data]
    if len(types_present) <= 1:
        return [data]
    base = {"version": data["version"]} if "version" in data else {}
    return [{**base, t: data[t]} for t in types_present]


def _repair_catalog_id(msg: dict, valid_catalog_id: str) -> None:
    """Overwrite a bad createSurface.catalogId with the session's active value."""
    create_surface = msg.get("createSurface")
    if not isinstance(create_surface, dict):
        return
    actual = create_surface.get("catalogId")
    if actual == valid_catalog_id:
        return
    logger.warning(
        "Repairing invalid createSurface.catalogId %r -> %r",
        actual, valid_catalog_id,
    )
    create_surface["catalogId"] = valid_catalog_id


_A2UI_BLOB_MARKER = "<a2a_datapart_json>"
_A2UI_BLOB_MARKER_END = "</a2a_datapart_json>"


def _make_a2ui_blob_part(a2ui_data: dict) -> dict:
    """Create an inline_data part wrapped in a2a_datapart_json markers for GE.

    Gemini Enterprise's streaming_agent_run_with_events path extracts A2UI
    DataParts by looking for <a2a_datapart_json> XML markers in text/plain
    blobs — it does NOT support raw application/a2ui+json inline_data.
    """
    datapart_json = json.dumps({
        "kind": "data",
        "metadata": {"mimeType": A2UI_MIME_TYPE},
        "data": a2ui_data,
    })
    blob_data = _A2UI_BLOB_MARKER + datapart_json + _A2UI_BLOB_MARKER_END
    return {
        "inline_data": {
            "data": base64.b64encode(blob_data.encode("utf-8")).decode(),
            "mime_type": "text/plain",
        }
    }


def _get_catalog_id_from_agent() -> str | None:
    """Get the catalog ID from the agent's schema manager."""
    try:
        from app.agent import schema_manager
        catalog = schema_manager.get_selected_catalog()
        if hasattr(catalog, "id"):
            return catalog.id
        if hasattr(catalog, "catalog_id"):
            return catalog.catalog_id
        # Try to get from the config
        config = catalog
        if hasattr(config, "url"):
            return config.url
    except Exception:
        pass
    return None


def _process_event_dict(event_dict: dict) -> dict:
    """Process a serialized ADK event dict to convert A2UI function responses to blob parts.

    Looks for function_response parts with the send_a2ui_json_to_client tool
    that contain validated_a2ui_json, and replaces them with inline_data blob
    parts.
    """
    content = event_dict.get("content")
    if not content:
        return event_dict

    parts = content.get("parts")
    if not parts:
        return event_dict

    new_parts = []
    modified = False
    valid_catalog_id = _get_catalog_id_from_agent()

    for part in parts:
        fn_response = part.get("function_response")
        if not fn_response:
            new_parts.append(part)
            continue

        # Check if this is the A2UI tool response
        if fn_response.get("name") != TOOL_NAME:
            new_parts.append(part)
            continue

        response = fn_response.get("response", {})
        a2ui_payload = response.get(VALIDATED_A2UI_JSON_KEY)
        if not a2ui_payload:
            new_parts.append(part)
            continue

        # Convert validated A2UI JSON to blob parts
        modified = True
        logger.info("Converting A2UI tool response to %d blob parts", len(a2ui_payload))

        for a2ui_msg in a2ui_payload:
            # Split combined messages
            for split_msg in _split_combined_a2ui_data(a2ui_msg):
                # Rewrite maps proxy URLs
                split_msg = _replace_proxy_urls(split_msg)
                # Repair catalog ID
                if valid_catalog_id:
                    _repair_catalog_id(split_msg, valid_catalog_id)
                # Create blob part
                new_parts.append(_make_a2ui_blob_part(split_msg))

    if modified:
        # Also strip validated_a2ui_json from text parts in the same event.
        # The model sometimes echoes the raw JSON in its text output alongside
        # the function call. Since we've converted the payload to blobs, the
        # text version is redundant and confusing.
        cleaned_parts = []
        for part in new_parts:
            text = part.get("text") if isinstance(part, dict) else None
            if text and VALIDATED_A2UI_JSON_KEY in str(text):
                # Strip from the start of the JSON blob to the end
                idx = str(text).find('{"' + VALIDATED_A2UI_JSON_KEY + '"')
                if idx >= 0:
                    cleaned_text = str(text)[:idx].rstrip()
                    if cleaned_text:
                        cleaned_parts.append({**part, "text": cleaned_text})
                        logger.info(
                            "Stripped validated_a2ui_json from text part "
                            "(was %d chars, now %d)", len(str(text)), len(cleaned_text)
                        )
                    else:
                        logger.info("Dropped empty text part after stripping a2ui JSON")
                    continue
            cleaned_parts.append(part)
        event_dict = {**event_dict}
        event_dict["content"] = {**content, "parts": cleaned_parts}

    return event_dict


# --------------------------------------------------------------------------- #
# AgentEngineApp with A2UI support
# --------------------------------------------------------------------------- #

class AgentEngineApp(AdkApp):
    def set_up(self) -> None:
        """Initialize the agent engine app with logging and telemetry."""
        vertexai.init()
        setup_telemetry()
        super().set_up()
        logging.basicConfig(level=logging.INFO)
        logging_client = google_cloud_logging.Client()
        self.logger = logging_client.logger(__name__)
        if gemini_location:
            os.environ["GOOGLE_CLOUD_LOCATION"] = gemini_location

    async def streaming_agent_run_with_events(self, request_json: str):
        """Override to intercept events and inject A2UI blobs into model text events.

        GE only renders A2UI blobs when they appear alongside text parts in
        model response events (like v0.8's after_model_callback). The SDK emits
        A2UI data as separate function_response events in DIFFERENT chunks,
        so we must buffer ALL chunks to splice blobs into the correct text event.
        """
        # Buffer all chunks — we need cross-chunk blob injection
        all_chunks = []
        async for response_chunk in super().streaming_agent_run_with_events(request_json):
            all_chunks.append(response_chunk)

        logger.info("Buffered %d total response chunks", len(all_chunks))

        # Flatten: collect all events across all chunks, process them
        all_processed_events = []  # list of (chunk_idx, event_dict)
        pending_blobs = []

        for chunk_idx, response_chunk in enumerate(all_chunks):
            if not (isinstance(response_chunk, dict) and "events" in response_chunk):
                continue

            events = response_chunk["events"]
            logger.info("  chunk %d: %d events", chunk_idx, len(events))

            for i, event_dict in enumerate(events):
                content = event_dict.get("content", {})
                parts = content.get("parts", []) if isinstance(content, dict) else []

                # Log event parts
                part_types = []
                for p in parts:
                    if isinstance(p, dict):
                        if p.get("function_response"):
                            fr = p["function_response"]
                            resp_keys = list(fr.get("response", {}).keys()) if isinstance(fr.get("response"), dict) else []
                            part_types.append(f"fn_resp(name={fr.get('name')},keys={resp_keys})")
                        elif p.get("text") is not None:
                            part_types.append(f"text(len={len(str(p['text']))})")
                        elif p.get("inline_data"):
                            part_types.append(f"blob(mime={p['inline_data'].get('mime_type')})")
                        else:
                            part_types.append(f"other({[k for k,v in p.items() if v is not None]})")
                logger.info("    event[%d]: %s", i, part_types)

                # Process the event (converts fn_resp to blobs + strips text)
                processed = _process_event_dict(event_dict)
                proc_content = processed.get("content", {})
                proc_parts = proc_content.get("parts", []) if isinstance(proc_content, dict) else []

                # Separate blob parts from non-blob parts
                event_blobs = [p for p in proc_parts if isinstance(p, dict) and p.get("inline_data")]
                event_other = [p for p in proc_parts if not (isinstance(p, dict) and p.get("inline_data"))]

                if event_blobs:
                    pending_blobs.extend(event_blobs)
                    logger.info("    -> extracted %d blob parts", len(event_blobs))

                # Keep event if it has non-blob content
                if event_other:
                    evt = {**processed}
                    evt["content"] = {**proc_content, "parts": event_other}
                    all_processed_events.append((chunk_idx, evt))
                elif not event_blobs:
                    all_processed_events.append((chunk_idx, processed))

        # Inject pending blobs into the last text event (cross-chunk)
        if pending_blobs:
            injected = False
            for j in range(len(all_processed_events) - 1, -1, -1):
                _, evt = all_processed_events[j]
                evt_content = evt.get("content", {})
                evt_parts = evt_content.get("parts", []) if isinstance(evt_content, dict) else []
                has_text = any(isinstance(p, dict) and p.get("text") is not None for p in evt_parts)
                if has_text:
                    new_parts = list(evt_parts) + pending_blobs
                    evt = {**evt}
                    evt["content"] = {**evt_content, "parts": new_parts}
                    all_processed_events[j] = (all_processed_events[j][0], evt)
                    logger.info(
                        "Injected %d A2UI blob(s) into event (now %d parts total)",
                        len(pending_blobs), len(new_parts),
                    )
                    injected = True
                    break

            if not injected:
                logger.warning("No text event found — appending blobs as synthetic event")
                synthetic = {"content": {"parts": [{"text": ""}] + pending_blobs, "role": "model"}}
                # Append to the last chunk
                last_chunk_idx = len(all_chunks) - 1
                all_processed_events.append((last_chunk_idx, synthetic))

        # Reassemble chunks with processed events
        for chunk_idx, response_chunk in enumerate(all_chunks):
            if isinstance(response_chunk, dict) and "events" in response_chunk:
                chunk_events = [evt for ci, evt in all_processed_events if ci == chunk_idx]
                response_chunk = {**response_chunk, "events": chunk_events}
            yield response_chunk

    def register_feedback(self, feedback: dict[str, Any]) -> None:
        """Collect and log feedback."""
        feedback_obj = Feedback.model_validate(feedback)
        self.logger.log_struct(feedback_obj.model_dump(), severity="INFO")

    def register_operations(self) -> dict[str, list[str]]:
        """Registers the operations of the Agent."""
        operations = super().register_operations()
        operations[""] = [*operations.get("", []), "register_feedback"]
        return operations

    def clone(self) -> "AgentEngineApp":
        """Returns a clone of the Agent Runtime application."""
        return self


gemini_location = os.environ.get("GOOGLE_CLOUD_LOCATION")
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")
agent_runtime = AgentEngineApp(
    app=adk_app,
    artifact_service_builder=lambda: (
        GcsArtifactService(bucket_name=logs_bucket_name)
        if logs_bucket_name
        else InMemoryArtifactService()
    ),
)


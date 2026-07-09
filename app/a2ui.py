"""A2UI envelope builders + optional SDK adapter.

Targets **v0.9** — the latest fully-supported catalog and envelope
format. The SDK's ``A2uiSchemaManager`` validates payloads against the
v0.9 basic catalog schema.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .widgets.base import Widget


A2UI_VERSION = "v0.9"
A2UI_BASIC_CATALOG_ID = (
    "https://a2ui.org/specification/v0_9/basic_catalog.json"
)


def _envelope(kind: str, payload: dict) -> dict:
    """Wrap a message payload in the standard A2UI envelope."""

    return {"version": A2UI_VERSION, kind: payload}


def create_surface(
    surface_id: str,
    widget: "Widget",
    catalog_id: str = A2UI_BASIC_CATALOG_ID,
    agent_display_name: str | None = None,
) -> dict:
    """Build a ``createSurface`` envelope for a single widget."""

    inner: dict[str, Any] = {
        "surfaceId": surface_id,
        "catalogId": catalog_id,
        "components": widget.to_components(),
    }
    dm = widget.to_data_model()
    if dm:
        inner["dataModel"] = dm
    if agent_display_name:
        inner["surfaceProperties"] = {"agentDisplayName": agent_display_name}
    return _envelope("createSurface", inner)


def update_components(surface_id: str, widget: "Widget") -> dict:
    """Build an ``updateComponents`` envelope."""

    return _envelope(
        "updateComponents",
        {"surfaceId": surface_id, "components": widget.to_components()},
    )


def update_data_model(surface_id: str, path: str, value: Any) -> dict:
    """Build a JSON-Pointer patch envelope."""

    payload: dict[str, Any] = {"surfaceId": surface_id, "path": path}
    if value is not None:
        payload["value"] = value
    return _envelope("updateDataModel", payload)


def delete_surface(surface_id: str) -> dict:
    """Build a ``deleteSurface`` envelope."""

    return _envelope("deleteSurface", {"surfaceId": surface_id})


def widget_to_a2ui_stream(surface_id: str, widget: "Widget") -> list[dict]:
    """Emit a full stream: ``createSurface`` + one ``updateDataModel`` if
    the widget contributes to the data model."""

    stream: list[dict] = [create_surface(surface_id, widget)]
    dm = widget.to_data_model()
    if dm:
        stream.append(update_data_model(surface_id, "/", dm))
    return stream


# ---------------------------------------------------------------
# Optional SDK adapter
# ---------------------------------------------------------------
def _shim_create_a2ui_part(payload: dict, version: str | None = None) -> dict:
    """Fallback ``create_a2ui_part`` when the a2ui-agent-sdk is missing.

    Produces a dict shaped like an A2A ``DataPart`` so the downstream
    transport code doesn't have to branch on which implementation
    produced it.
    """

    return {
        "kind": "data",
        "data": payload,
        "metadata": {
            "mimeType": "application/a2ui+json",
            "a2uiVersion": version or A2UI_VERSION,
            "source": "a2ui_starter.shim",
        },
    }


def try_import_sdk() -> Callable[..., Any]:
    """Return the real ``create_a2ui_part`` if importable, else a shim.

    TODO(sanchit): switch to the real SDK once we've stabilised on
    ``a2ui-agent-sdk >= 0.4.0``. The shim matches the SDK's DataPart
    shape closely enough for local preview + tests.
    """

    try:  # pragma: no cover - depends on optional extra
        from a2ui.a2a.parts import create_a2ui_part  # type: ignore

        return create_a2ui_part
    except Exception:  # noqa: BLE001
        return _shim_create_a2ui_part

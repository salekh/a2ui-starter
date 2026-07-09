"""Tests for the envelope builders in ``a2ui.py``."""

from __future__ import annotations

from app.a2ui import (
    A2UI_BASIC_CATALOG_ID,
    A2UI_VERSION,
    create_surface,
    delete_surface,
    update_components,
    update_data_model,
    widget_to_a2ui_stream,
)
from app.sample_data import sample_data_table, sample_rich_text


def test_version_is_v09() -> None:
    assert A2UI_VERSION == "v0.9"


def test_catalog_id_is_v09() -> None:
    assert "v0_9" in A2UI_BASIC_CATALOG_ID


def test_create_surface_shape() -> None:
    widget = sample_rich_text()
    env = create_surface("s1", widget, agent_display_name="Weather Bot")
    assert env["version"] == "v0.9"
    inner = env["createSurface"]
    assert inner["surfaceId"] == "s1"
    assert inner["catalogId"] == A2UI_BASIC_CATALOG_ID
    assert isinstance(inner["components"], list) and inner["components"]
    assert inner["surfaceProperties"] == {"agentDisplayName": "Weather Bot"}


def test_create_surface_carries_data_model_when_widget_supplies_it() -> None:
    widget = sample_data_table()
    env = create_surface("t1", widget)
    inner = env["createSurface"]
    assert "dataModel" in inner
    assert "rows" in inner["dataModel"]
    assert len(inner["dataModel"]["rows"]) == len(widget.rows)


def test_update_components_shape() -> None:
    widget = sample_rich_text()
    env = update_components("s1", widget)
    assert env["version"] == "v0.9"
    inner = env["updateComponents"]
    assert inner["surfaceId"] == "s1"
    assert isinstance(inner["components"], list) and inner["components"]


def test_update_data_model_and_delete_surface_shapes() -> None:
    env = update_data_model("s1", "/user/name", "Jane")
    inner = env["updateDataModel"]
    assert inner == {"surfaceId": "s1", "path": "/user/name", "value": "Jane"}

    env2 = delete_surface("s1")
    assert env2["deleteSurface"] == {"surfaceId": "s1"}
    assert env2["version"] == "v0.9"


def test_widget_to_a2ui_stream_starts_with_create_surface() -> None:
    widget = sample_data_table()
    stream = widget_to_a2ui_stream("s1", widget)
    assert len(stream) >= 1
    first = stream[0]
    assert "createSurface" in first
    # data-table contributes a data model, so we should also get an update
    assert any("updateDataModel" in msg for msg in stream)

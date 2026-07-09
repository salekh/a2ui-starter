"""Round-trip + structural tests for every rich widget."""

from __future__ import annotations

import json

import pytest

from app.sample_data import (
    sample_action_buttons,
    sample_callouts,
    sample_card,
    sample_citation_source,
    sample_data_table,
    sample_key_value_list,
    sample_metric_tiles,
    sample_rich_text,
    sample_tag_chip,
    sample_timeline,
)
from app.widgets import Widget


def _all_instances() -> list[Widget]:
    widgets: list[Widget] = [
        sample_rich_text(),
        sample_data_table(),
        sample_tag_chip(),
        sample_card(),
        sample_key_value_list(),
        sample_citation_source(),
        sample_timeline(),
        sample_action_buttons(),
    ]
    widgets.extend(sample_metric_tiles())
    widgets.extend(sample_callouts())
    return widgets


@pytest.fixture(params=_all_instances(), ids=lambda w: w.__class__.__name__ + ":" + w.id)
def widget(request) -> Widget:
    return request.param


def test_components_nonempty_and_root_id_present(widget: Widget) -> None:
    comps = widget.to_components()
    assert comps, "to_components() must return a non-empty list"
    ids = [c["id"] for c in comps]
    assert widget.id in ids, "root id must be present in components"


def test_component_ids_are_unique(widget: Widget) -> None:
    comps = widget.to_components()
    ids = [c["id"] for c in comps]
    assert len(ids) == len(set(ids)), f"duplicate component ids: {ids}"


def test_all_referenced_children_exist(widget: Widget) -> None:
    comps = widget.to_components()
    known = {c["id"] for c in comps}
    for c in comps:
        # children may be array-of-ids, {componentId,path}, or missing.
        ch = c.get("children")
        if isinstance(ch, list):
            for cid in ch:
                assert cid in known, f"child {cid!r} of {c['id']!r} not in adjacency list"
        elif isinstance(ch, dict):
            assert "componentId" in ch and "path" in ch
            assert ch["componentId"] in known, (
                f"template child {ch['componentId']!r} of {c['id']!r} missing"
            )
        # Card + Button use "child" (single id)
        single = c.get("child")
        if isinstance(single, str):
            assert single in known, (
                f"single child {single!r} of {c['id']!r} not in adjacency list"
            )
        # Tabs would use "tabs": [{title, child}, ...]  — none of our widgets do,
        # but keep the check open in case someone adds one.
        tabs = c.get("tabs")
        if isinstance(tabs, list):
            for t in tabs:
                assert t.get("child") in known


def test_json_round_trip(widget: Widget) -> None:
    dumped = json.dumps(widget.to_a2ui_json())
    loaded = json.loads(dumped)
    rebuilt = type(widget).from_a2ui_json(loaded)
    assert rebuilt == widget
    # And Widget.from_a2ui_json dispatches to the same subclass
    dispatched = Widget.from_a2ui_json(loaded)
    assert isinstance(dispatched, type(widget))
    assert dispatched == widget

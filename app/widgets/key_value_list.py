"""KeyValueList — Column of Rows, each with a key Text + value Text."""

from __future__ import annotations

from typing import ClassVar

from .base import Widget, build_accessibility, find_component, get_stash


class KeyValueList(Widget):
    type_marker: ClassVar[str] = "KeyValueList"

    items: list[tuple[str, str]]

    def to_components(self) -> list[dict]:
        column_id = self.id
        row_ids = [f"{self.id}__r{i}" for i in range(len(self.items))]
        comps: list[dict] = [
            {
                "id": column_id,
                "component": "Column",
                "children": row_ids,
                "accessibility": build_accessibility(
                    self.accessibility_label,
                    self.type_marker,
                    stash=self.model_dump(),
                ),
            }
        ]
        for row_id, (key, value) in zip(row_ids, self.items):
            key_id = f"{row_id}__k"
            val_id = f"{row_id}__v"
            comps.append(
                {
                    "id": row_id,
                    "component": "Row",
                    "children": [key_id, val_id],
                    "justify": "spaceBetween",
                }
            )
            comps.append(
                {
                    "id": key_id,
                    "component": "Text",
                    "text": key,
                    "variant": "body",
                    "accessibility": {"description": "title-medium"},
                }
            )
            comps.append(
                {
                    "id": val_id,
                    "component": "Text",
                    "text": value,
                    "variant": "body",
                }
            )
        return comps

    @classmethod
    def from_components(
        cls,
        components: list[dict],
        root_id: str,
        data_model: dict | None = None,
    ) -> "KeyValueList":
        root = find_component(components, root_id)
        stash = get_stash(root) or {}
        # tuples come back from JSON as lists — Pydantic will coerce
        return cls(**stash)

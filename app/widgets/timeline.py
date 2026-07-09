"""Timeline — Column of Rows with a state Icon + Column of Texts."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from .base import Widget, build_accessibility, find_component, get_stash


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    timestamp: str
    state: Literal["done", "active", "pending", "error"] = "pending"
    description: str | None = None


_STATE_ICON = {
    "done": "check",
    "active": "play",
    "pending": "pause",
    "error": "error",
}


class Timeline(Widget):
    type_marker: ClassVar[str] = "Timeline"

    steps: list[Step]

    def to_components(self) -> list[dict]:
        column_id = self.id
        row_ids: list[str] = []
        extra: list[dict] = []
        for i, step in enumerate(self.steps):
            row_id = f"{self.id}__r{i}"
            icon_id = f"{row_id}__ico"
            col_id = f"{row_id}__col"
            title_id = f"{row_id}__title"
            ts_id = f"{row_id}__ts"
            desc_id = f"{row_id}__desc" if step.description else None
            row_ids.append(row_id)
            extra.extend(
                [
                    {
                        "id": row_id,
                        "component": "Row",
                        "children": [icon_id, col_id],
                        "align": "start",
                    },
                    {
                        "id": icon_id,
                        "component": "Icon",
                        "name": _STATE_ICON.get(step.state, "info"),
                        "accessibility": {
                            "description": f"state={step.state}",
                        },
                    },
                    {
                        "id": col_id,
                        "component": "Column",
                        "children": [title_id, ts_id]
                        + ([desc_id] if desc_id else []),
                    },
                    {
                        "id": title_id,
                        "component": "Text",
                        "text": step.title,
                        "variant": "body",
                        "accessibility": {"description": "title-medium"},
                    },
                    {
                        "id": ts_id,
                        "component": "Text",
                        "text": step.timestamp,
                        "variant": "caption",
                    },
                ]
            )
            if desc_id:
                extra.append(
                    {
                        "id": desc_id,
                        "component": "Text",
                        "text": step.description,
                        "variant": "body",
                    }
                )
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
        comps.extend(extra)
        return comps

    @classmethod
    def from_components(
        cls,
        components: list[dict],
        root_id: str,
        data_model: dict | None = None,
    ) -> "Timeline":
        root = find_component(components, root_id)
        stash = get_stash(root) or {}
        return cls(**stash)

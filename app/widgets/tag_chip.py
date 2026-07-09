"""TagChip — a Row with an optional Icon + Text (label-large)."""

from __future__ import annotations

from typing import ClassVar, Literal

from .base import Widget, build_accessibility, find_component, get_stash


class TagChip(Widget):
    type_marker: ClassVar[str] = "TagChip"

    label: str
    variant: Literal["assist", "filter", "input", "suggestion"] = "assist"
    intent: Literal["neutral", "success", "warning", "error", "info"] = "neutral"
    icon: str | None = None  # optional Icon name from the basic catalog

    def to_components(self) -> list[dict]:
        row_id = self.id
        icon_id = f"{self.id}__icon" if self.icon else None
        label_id = f"{self.id}__label"

        row_children: list[str] = []
        if icon_id:
            row_children.append(icon_id)
        row_children.append(label_id)

        comps: list[dict] = [
            {
                "id": row_id,
                "component": "Row",
                "children": row_children,
                "align": "center",
                "accessibility": build_accessibility(
                    self.accessibility_label,
                    self.type_marker,
                    stash=self.model_dump(),
                    extra_description=f"chip:{self.variant}/{self.intent}",
                ),
            }
        ]
        if icon_id:
            comps.append(
                {
                    "id": icon_id,
                    "component": "Icon",
                    "name": self.icon,
                }
            )
        comps.append(
            {
                "id": label_id,
                "component": "Text",
                "text": self.label,
                "variant": "body",
                "accessibility": {"description": "label-large"},
            }
        )
        return comps

    @classmethod
    def from_components(
        cls,
        components: list[dict],
        root_id: str,
        data_model: dict | None = None,
    ) -> "TagChip":
        root = find_component(components, root_id)
        stash = get_stash(root) or {}
        return cls(**stash)

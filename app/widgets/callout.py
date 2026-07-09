"""Callout — Card > Row > [Icon, Column > [title Text, body Text]]."""

from __future__ import annotations

from typing import ClassVar, Literal

from .base import Widget, build_accessibility, find_component, get_stash


_VARIANT_ICON = {
    "info": "info",
    "success": "check",
    "warning": "warning",
    "error": "error",
}


class Callout(Widget):
    type_marker: ClassVar[str] = "Callout"

    title: str
    body: str
    variant: Literal["info", "success", "warning", "error"] = "info"

    def to_components(self) -> list[dict]:
        card_id = self.id
        row_id = f"{self.id}__row"
        icon_id = f"{self.id}__icon"
        col_id = f"{self.id}__col"
        title_id = f"{self.id}__title"
        body_id = f"{self.id}__body"

        return [
            {
                "id": card_id,
                "component": "Card",
                "child": row_id,
                "accessibility": build_accessibility(
                    self.accessibility_label,
                    self.type_marker,
                    stash=self.model_dump(),
                    extra_description=f"callout:{self.variant}",
                ),
            },
            {
                "id": row_id,
                "component": "Row",
                "children": [icon_id, col_id],
                "align": "start",
            },
            {
                "id": icon_id,
                "component": "Icon",
                "name": _VARIANT_ICON.get(self.variant, "info"),
            },
            {
                "id": col_id,
                "component": "Column",
                "children": [title_id, body_id],
            },
            {
                "id": title_id,
                "component": "Text",
                "text": self.title,
                "variant": "body",
                "accessibility": {"description": "title-medium"},
            },
            {
                "id": body_id,
                "component": "Text",
                "text": self.body,
                "variant": "body",
            },
        ]

    @classmethod
    def from_components(
        cls,
        components: list[dict],
        root_id: str,
        data_model: dict | None = None,
    ) -> "Callout":
        root = find_component(components, root_id)
        stash = get_stash(root) or {}
        return cls(**stash)

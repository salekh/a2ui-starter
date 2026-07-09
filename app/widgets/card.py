"""Card — Card > Column > [title Text, optional subtitle Text, body Text]."""

from __future__ import annotations

from typing import ClassVar

from .base import Widget, build_accessibility, find_component, get_stash


class Card(Widget):
    type_marker: ClassVar[str] = "Card"

    title: str
    body: str
    subtitle: str | None = None

    def to_components(self) -> list[dict]:
        card_id = self.id
        column_id = f"{self.id}__col"
        title_id = f"{self.id}__title"
        subtitle_id = f"{self.id}__subtitle" if self.subtitle else None
        body_id = f"{self.id}__body"

        col_children = [title_id]
        if subtitle_id:
            col_children.append(subtitle_id)
        col_children.append(body_id)

        comps: list[dict] = [
            {
                "id": card_id,
                "component": "Card",
                "child": column_id,
                "accessibility": build_accessibility(
                    self.accessibility_label,
                    self.type_marker,
                    stash=self.model_dump(),
                ),
            },
            {
                "id": column_id,
                "component": "Column",
                "children": col_children,
            },
            {
                "id": title_id,
                "component": "Text",
                "text": self.title,
                "variant": "body",
                "accessibility": {"description": "title-large"},
            },
        ]
        if subtitle_id:
            comps.append(
                {
                    "id": subtitle_id,
                    "component": "Text",
                    "text": self.subtitle,
                    "variant": "caption",
                }
            )
        comps.append(
            {
                "id": body_id,
                "component": "Text",
                "text": self.body,
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
    ) -> "Card":
        root = find_component(components, root_id)
        stash = get_stash(root) or {}
        return cls(**stash)

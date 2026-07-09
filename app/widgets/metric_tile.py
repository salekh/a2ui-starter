"""MetricTile — Card > Column > [label Text, Row > (value Text large, delta Text)]."""

from __future__ import annotations

from typing import ClassVar, Literal, Union

from .base import Widget, build_accessibility, find_component, get_stash


class MetricTile(Widget):
    type_marker: ClassVar[str] = "MetricTile"

    label: str
    value: Union[str, int, float]
    delta: str | None = None
    delta_direction: Literal["up", "down", "flat"] | None = None

    def to_components(self) -> list[dict]:
        card_id = self.id
        col_id = f"{self.id}__col"
        label_id = f"{self.id}__label"
        row_id = f"{self.id}__row"
        value_id = f"{self.id}__value"
        delta_id = f"{self.id}__delta" if self.delta else None

        row_children = [value_id]
        if delta_id:
            row_children.append(delta_id)

        comps: list[dict] = [
            {
                "id": card_id,
                "component": "Card",
                "child": col_id,
                "accessibility": build_accessibility(
                    self.accessibility_label,
                    self.type_marker,
                    stash=self.model_dump(),
                ),
            },
            {
                "id": col_id,
                "component": "Column",
                "children": [label_id, row_id],
            },
            {
                "id": label_id,
                "component": "Text",
                "text": self.label,
                "variant": "caption",
                "accessibility": {"description": "label-medium"},
            },
            {
                "id": row_id,
                "component": "Row",
                "children": row_children,
                "align": "center",
            },
            {
                "id": value_id,
                "component": "Text",
                "text": str(self.value),
                "variant": "body",
                "accessibility": {"description": "display-small; tabular-nums"},
            },
        ]
        if delta_id:
            comps.append(
                {
                    "id": delta_id,
                    "component": "Text",
                    "text": self.delta,
                    "variant": "caption",
                    "accessibility": {
                        "description": (
                            f"label-medium; delta_direction={self.delta_direction or 'flat'}"
                        )
                    },
                }
            )
        return comps

    @classmethod
    def from_components(
        cls,
        components: list[dict],
        root_id: str,
        data_model: dict | None = None,
    ) -> "MetricTile":
        root = find_component(components, root_id)
        stash = get_stash(root) or {}
        return cls(**stash)

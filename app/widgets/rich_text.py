"""RichText widget — a markdown-ish body of text rendered as a Column of Text."""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field

from .base import Widget, build_accessibility, find_component, get_stash


class RichText(Widget):
    """Multi-paragraph markdown-ish text.

    Renders as a ``Column`` of ``Text`` components (one per paragraph).
    """

    type_marker: ClassVar[str] = "RichText"

    text: str = Field(min_length=1)

    def _paragraphs(self) -> list[str]:
        return [p.strip() for p in self.text.split("\n\n") if p.strip()] or [self.text]

    def to_components(self) -> list[dict]:
        paragraphs = self._paragraphs()
        child_ids = [f"{self.id}__p{i}" for i in range(len(paragraphs))]
        comps: list[dict] = [
            {
                "id": self.id,
                "component": "Column",
                "children": child_ids,
                "accessibility": build_accessibility(
                    self.accessibility_label,
                    self.type_marker,
                    stash=self.model_dump(),
                ),
            }
        ]
        for cid, para in zip(child_ids, paragraphs):
            comps.append(
                {
                    "id": cid,
                    "component": "Text",
                    "text": para,
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
    ) -> "RichText":
        root = find_component(components, root_id)
        stash = get_stash(root) or {}
        return cls(**stash)

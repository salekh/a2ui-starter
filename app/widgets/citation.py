"""CitationSource — Card > Column > List of nested Cards, one per source."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from .base import Widget, build_accessibility, find_component, get_stash


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    url: str
    snippet: str
    domain: str
    favicon_url: str | None = None


class CitationSource(Widget):
    type_marker: ClassVar[str] = "CitationSource"

    sources: list[Source]
    title: str = "Sources"

    def to_components(self) -> list[dict]:
        card_id = self.id
        column_id = f"{self.id}__col"
        title_id = f"{self.id}__title"
        list_id = f"{self.id}__list"

        source_ids: list[str] = []
        source_components: list[dict] = []
        for i, src in enumerate(self.sources):
            src_card_id = f"{self.id}__src{i}"
            src_col_id = f"{src_card_id}__col"
            row_id = f"{src_card_id}__row"
            fav_id = f"{src_card_id}__fav" if src.favicon_url else None
            head_id = f"{src_card_id}__head"
            snip_id = f"{src_card_id}__snip"

            source_ids.append(src_card_id)
            source_components.extend(
                [
                    {
                        "id": src_card_id,
                        "component": "Card",
                        "child": src_col_id,
                    },
                    {
                        "id": src_col_id,
                        "component": "Column",
                        "children": [row_id, snip_id],
                    },
                    {
                        "id": row_id,
                        "component": "Row",
                        "children": ([fav_id] if fav_id else []) + [head_id],
                        "align": "center",
                    },
                ]
            )
            if fav_id:
                source_components.append(
                    {
                        "id": fav_id,
                        "component": "Image",
                        "url": src.favicon_url,
                        "variant": "icon",
                    }
                )
            source_components.append(
                {
                    "id": head_id,
                    "component": "Text",
                    "text": f"{src.title} — {src.domain}",
                    "variant": "body",
                    "accessibility": {
                        "description": f"title-small; url={src.url}",
                    },
                }
            )
            source_components.append(
                {
                    "id": snip_id,
                    "component": "Text",
                    "text": src.snippet,
                    "variant": "caption",
                }
            )

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
                "children": [title_id, list_id],
            },
            {
                "id": title_id,
                "component": "Text",
                "text": self.title,
                "variant": "body",
                "accessibility": {"description": "title-large"},
            },
            {
                "id": list_id,
                "component": "List",
                "children": source_ids,
                "direction": "vertical",
            },
        ]
        comps.extend(source_components)
        return comps

    @classmethod
    def from_components(
        cls,
        components: list[dict],
        root_id: str,
        data_model: dict | None = None,
    ) -> "CitationSource":
        root = find_component(components, root_id)
        stash = get_stash(root) or {}
        return cls(**stash)

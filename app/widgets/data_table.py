"""DataTable — Card > Column > (header Row + body List of Rows bound to /rows)."""

from __future__ import annotations

from typing import ClassVar, Union

from pydantic import BaseModel, ConfigDict, Field

from .base import Widget, build_accessibility, find_component, get_stash


class Column(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str
    header: str
    align: str = "left"  # "left" | "right" | "center"


CellValue = Union[str, int, float]


class DataTable(Widget):
    type_marker: ClassVar[str] = "DataTable"

    title: str | None = None
    columns: list[Column] = Field(default_factory=list)
    rows: list[dict[str, CellValue]] = Field(default_factory=list)

    def to_components(self) -> list[dict]:
        card_id = self.id
        column_id = f"{self.id}__col"
        header_row_id = f"{self.id}__hdr"
        header_cell_ids = [f"{self.id}__hdr_{c.key}" for c in self.columns]
        body_list_id = f"{self.id}__list"
        template_row_id = f"{self.id}__tpl"
        template_cell_ids = [f"{self.id}__tpl_{c.key}" for c in self.columns]
        title_id = f"{self.id}__title" if self.title else None

        column_children: list[str] = []
        if title_id:
            column_children.append(title_id)
        column_children.extend([header_row_id, body_list_id])

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
                "children": column_children,
            },
        ]
        if title_id:
            comps.append(
                {
                    "id": title_id,
                    "component": "Text",
                    "text": self.title,
                    "variant": "body",
                }
            )
        comps.append(
            {
                "id": header_row_id,
                "component": "Row",
                "children": header_cell_ids,
            }
        )
        for cid, col in zip(header_cell_ids, self.columns):
            comps.append(
                {
                    "id": cid,
                    "component": "Text",
                    "text": col.header,
                    "variant": "body",
                    "accessibility": {"description": f"title-small; align={col.align}"},
                }
            )
        comps.append(
            {
                "id": body_list_id,
                "component": "List",
                "children": {"componentId": template_row_id, "path": "/rows"},
                "direction": "vertical",
            }
        )
        comps.append(
            {
                "id": template_row_id,
                "component": "Row",
                "children": template_cell_ids,
            }
        )
        for cid, col in zip(template_cell_ids, self.columns):
            comps.append(
                {
                    "id": cid,
                    "component": "Text",
                    "text": {"path": f"/{col.key}"},
                    "variant": "body",
                    "accessibility": {"description": f"align={col.align}"},
                }
            )
        return comps

    def to_data_model(self) -> dict:
        return {"rows": [dict(r) for r in self.rows]}

    @classmethod
    def from_components(
        cls,
        components: list[dict],
        root_id: str,
        data_model: dict | None = None,
    ) -> "DataTable":
        root = find_component(components, root_id)
        stash = get_stash(root) or {}
        return cls(**stash)

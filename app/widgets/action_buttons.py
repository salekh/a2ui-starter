"""ActionButtons — a Row of Buttons each with {event: {name, context, wantResponse: true}}."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import Widget, build_accessibility, find_component, get_stash


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    event_name: str
    variant: Literal["primary", "secondary", "tertiary"] = "primary"
    context: dict[str, Any] = Field(default_factory=dict)


class ActionButtons(Widget):
    type_marker: ClassVar[str] = "ActionButtons"

    actions: list[Action]

    def to_components(self) -> list[dict]:
        row_id = self.id
        button_ids: list[str] = []
        extras: list[dict] = []
        for i, action in enumerate(self.actions):
            btn_id = f"{self.id}__b{i}"
            label_id = f"{btn_id}__label"
            button_ids.append(btn_id)
            # v0.8 basic catalog: default / primary / borderless are the
            # supported button variants; map our tri-state to those.
            btn_variant = {
                "primary": "primary",
                "secondary": "default",
                "tertiary": "borderless",
            }.get(action.variant, "primary")
            extras.append(
                {
                    "id": btn_id,
                    "component": "Button",
                    "child": label_id,
                    "variant": btn_variant,
                    "action": {
                        "event": {
                            "name": action.event_name,
                            "context": action.context,
                            "wantResponse": True,
                        }
                    },
                }
            )
            extras.append(
                {
                    "id": label_id,
                    "component": "Text",
                    "text": action.label,
                    "variant": "body",
                    "accessibility": {"description": "label-large"},
                }
            )
        comps: list[dict] = [
            {
                "id": row_id,
                "component": "Row",
                "children": button_ids,
                "align": "center",
                "accessibility": build_accessibility(
                    self.accessibility_label,
                    self.type_marker,
                    stash=self.model_dump(),
                ),
            }
        ]
        comps.extend(extras)
        return comps

    @classmethod
    def from_components(
        cls,
        components: list[dict],
        root_id: str,
        data_model: dict | None = None,
    ) -> "ActionButtons":
        root = find_component(components, root_id)
        stash = get_stash(root) or {}
        return cls(**stash)

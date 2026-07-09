"""Base class for the composed rich widgets.

Every rich widget in this package inherits from :class:`Widget`. A widget
is a Pydantic v2 model that knows how to *compose itself* out of A2UI
Basic Catalog primitives (``Text``, ``Row``, ``Column``, ``Card``,
``List``, ``Button``, ``Icon``, ``Divider``).

Two directions:

* :meth:`Widget.to_components` — build the flat A2UI adjacency list
  rooted at ``self.id``.
* :meth:`Widget.from_components` — rebuild a ``Widget`` instance from a
  previously-emitted adjacency list.

The base class also provides an envelope-agnostic ``to_a2ui_json`` /
``from_a2ui_json`` pair so we can round-trip through JSON in tests.

Dispatch back to the correct subclass is done via a ``type_marker``
string that every widget embeds into its root component's
``accessibility.description``. This keeps the wire format valid A2UI
(``accessibility`` is a standard field on every component) while giving
us a deterministic hook for parsing.
"""

from __future__ import annotations

import base64
import json
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

# The marker prefix embedded in accessibility.description so we can
# recover the widget class on the way back in.
TYPE_MARKER_PREFIX = "a2ui-starter:widget="


def make_marker(marker: str) -> str:
    return f"{TYPE_MARKER_PREFIX}{marker}"


def parse_marker(description: str | None) -> str | None:
    if not description:
        return None
    for token in description.split(";"):
        token = token.strip()
        if token.startswith(TYPE_MARKER_PREFIX):
            return token[len(TYPE_MARKER_PREFIX) :]
    return None


class Widget(BaseModel):
    """Abstract-ish base for composed A2UI widgets.

    Subclasses MUST override :meth:`to_components`,
    :meth:`from_components`, and set a unique :attr:`type_marker`.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    accessibility_label: str | None = None

    # Subclasses set this. ``ClassVar`` so Pydantic doesn't try to make it
    # a field.
    type_marker: ClassVar[str] = "base"

    # ---------------------------------------------------------------
    # Subclass API
    # ---------------------------------------------------------------
    def to_components(self) -> list[dict]:  # pragma: no cover - abstract
        raise NotImplementedError

    def to_data_model(self) -> dict:  # default: no data-model contribution
        return {}

    @classmethod
    def from_components(
        cls,
        components: list[dict],
        root_id: str,
        data_model: dict | None = None,
    ) -> "Widget":  # pragma: no cover - abstract
        raise NotImplementedError

    # ---------------------------------------------------------------
    # Envelope helpers
    # ---------------------------------------------------------------
    def to_a2ui_json(self) -> dict:
        return {
            "components": self.to_components(),
            "dataModel": self.to_data_model(),
        }

    @classmethod
    def from_a2ui_json(cls, payload: dict) -> "Widget":
        """Dispatch back to the correct subclass via the ``type_marker``.

        We deliberately look up the subclass registry lazily to avoid
        an import cycle: subclasses register themselves at
        ``__init_subclass__`` time.
        """

        components: list[dict] = payload.get("components") or []
        data_model: dict = payload.get("dataModel") or {}
        if not components:
            raise ValueError("empty components list — nothing to decode")

        # Find the marker on the first component that has one; that
        # component's id is the root of the widget.
        marker = None
        root_id = None
        for comp in components:
            desc = (comp.get("accessibility") or {}).get("description")
            m = parse_marker(desc)
            if m:
                marker = m
                root_id = comp["id"]
                break

        if marker is None or root_id is None:
            raise ValueError(
                "no widget type_marker found in accessibility.description"
            )

        target = _WIDGET_REGISTRY.get(marker)
        if target is None:
            raise ValueError(f"unknown widget marker: {marker!r}")
        return target.from_components(components, root_id, data_model)

    # ---------------------------------------------------------------
    # Registry
    # ---------------------------------------------------------------
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        marker = getattr(cls, "type_marker", None)
        if marker and marker != "base":
            _WIDGET_REGISTRY[marker] = cls


# marker -> subclass
_WIDGET_REGISTRY: dict[str, type[Widget]] = {}


# ---------------------------------------------------------------
# Small helpers used by subclasses
# ---------------------------------------------------------------
def build_accessibility(
    label: str | None,
    marker: str,
    extra_description: str | None = None,
    stash: dict | None = None,
) -> dict:
    """Build an ``accessibility`` dict that carries our marker + optional stash."""

    description_parts = [make_marker(marker)]
    if stash is not None:
        description_parts.append(encode_stash(stash))
    if extra_description:
        description_parts.append(extra_description)
    out: dict[str, Any] = {"description": "; ".join(description_parts)}
    if label:
        out["label"] = label
    return out


def find_component(components: list[dict], comp_id: str) -> dict:
    for c in components:
        if c.get("id") == comp_id:
            return c
    raise KeyError(f"component id not found: {comp_id!r}")


STASH_PREFIX = "stash_b64:"


def encode_stash(payload: dict) -> str:
    """Serialize a small JSON payload into a base64 token safe for
    embedding inside ``accessibility.description``."""

    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return STASH_PREFIX + base64.b64encode(raw.encode("utf-8")).decode("ascii")


def decode_stash(description: str | None) -> dict | None:
    if not description:
        return None
    for token in description.split(";"):
        token = token.strip()
        if token.startswith(STASH_PREFIX):
            raw = base64.b64decode(
                token[len(STASH_PREFIX) :].encode("ascii")
            ).decode("utf-8")
            return json.loads(raw)
    return None


def get_extra_description(comp: dict) -> str | None:
    """Return the non-marker portion of a component's accessibility description."""

    desc = (comp.get("accessibility") or {}).get("description")
    if not desc:
        return None
    remainder = [
        tok.strip()
        for tok in desc.split(";")
        if not tok.strip().startswith(TYPE_MARKER_PREFIX)
        and not tok.strip().startswith(STASH_PREFIX)
    ]
    return "; ".join(remainder) if remainder else None


def get_stash(comp: dict) -> dict | None:
    return decode_stash((comp.get("accessibility") or {}).get("description"))

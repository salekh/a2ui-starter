"""FastAPI preview server.

Serves a self-contained HTML renderer that fetches ``/api/demo`` and
renders every widget stacked vertically. Also exposes per-widget
streams at ``/api/widget/{name}`` for isolated demos.

Includes the ``/maps/embed`` proxy for Google Maps Embed API.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from ..a2ui import widget_to_a2ui_stream
from ..sample_data import WIDGETS_BY_NAME, build_all_widgets

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"

app = FastAPI(title="a2ui_starter preview", version="0.2.0")
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def _root() -> RedirectResponse:
    return RedirectResponse(url="/preview")


@app.get("/preview", include_in_schema=False)
def _preview() -> FileResponse:
    return FileResponse(str(_INDEX_HTML), media_type="text/html")


@app.get("/api/demo")
def api_demo() -> list[dict]:
    """Return the full A2UI stream (createSurface + updateDataModel) for every widget."""

    stream: list[dict] = []
    for widget in build_all_widgets():
        surface_id = f"surface_{widget.id}"
        stream.extend(widget_to_a2ui_stream(surface_id, widget))
    return stream


@app.get("/api/widget/{name}")
def api_widget(name: str) -> list[dict]:
    """Return the isolated A2UI stream for a single widget by short name."""

    widget = WIDGETS_BY_NAME.get(name)
    if widget is None:
        raise HTTPException(
            status_code=404,
            detail=f"unknown widget: {name!r}. "
            f"Available: {sorted(WIDGETS_BY_NAME)}",
        )
    return widget_to_a2ui_stream(f"surface_{widget.id}", widget)


@app.get("/maps/embed")
async def maps_embed(mode: str = "place", q: str = "", origin: str = "", destination: str = ""):
    """Proxy endpoint that redirects to Google Maps Embed API with the real key.

    Query parameters:
        mode: Embed mode (place, directions, view, search, streetview).
        q: Search query (for mode=place and mode=search).
        origin: Origin address (for mode=directions).
        destination: Destination address (for mode=directions).
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return JSONResponse(
            {"error": "GOOGLE_MAPS_API_KEY not configured. "
             "Set the GOOGLE_MAPS_API_KEY environment variable."},
            status_code=500,
        )

    params = {}
    if mode in ("place", "search") and q:
        params["q"] = q
    elif mode == "directions":
        if origin:
            params["origin"] = origin
        if destination:
            params["destination"] = destination

    url = f"https://www.google.com/maps/embed/v1/{mode}?key={api_key}"
    if params:
        url += f"&{urlencode(params)}"

    return RedirectResponse(url=url)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}

"""Google Maps Embed API proxy.

Provides a ``/maps/embed`` endpoint that accepts map requests without an
API key and redirects to the Google Maps Embed API with the real key
injected server-side.  This keeps the API key out of A2UI payloads and
model output.

Usage in A2UI components::

    {"component": "WebFrameUrl",
     "url": "/maps/embed?mode=place&q=Google+Playa+Vista"}

The proxy reads ``GOOGLE_MAPS_API_KEY`` from the environment.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

logger = logging.getLogger(__name__)


def _get_maps_api_key() -> str | None:
    """Return the Google Maps API key from env."""
    return os.getenv("GOOGLE_MAPS_API_KEY")


async def maps_embed_handler(request: Request):
    """Proxy endpoint that redirects to Google Maps Embed API with the real key.

    Query parameters:
        mode: Embed mode (``place``, ``directions``, ``view``, ``search``,
              ``streetview``). Defaults to ``place``.
        All other query parameters are forwarded to the Embed API.
    """
    api_key = _get_maps_api_key()
    if not api_key:
        return JSONResponse(
            {"error": "GOOGLE_MAPS_API_KEY not configured"},
            status_code=500,
        )

    params = dict(request.query_params)
    mode = params.pop("mode", "place")

    url = f"https://www.google.com/maps/embed/v1/{mode}?key={api_key}"
    if params:
        url += f"&{urlencode(params)}"

    return RedirectResponse(url=url)


# Starlette Route to be mounted in the main app or preview server.
maps_embed_route = Route("/maps/embed", maps_embed_handler)

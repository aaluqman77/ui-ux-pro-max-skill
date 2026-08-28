#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI/UX Pro Max - remote MCP server (Streamable HTTP).

Membungkus mesin cari BM25 di ``src/ui-ux-pro-max/scripts/`` jadi tool MCP yang
bisa dipanggil dari Claude lewat Settings > Connectors. Tidak ada state, tidak
ada data pengguna, tidak ada tulis-menulis ke disk - murni query masuk, hasil
ranking keluar.

Env:
  PORT        diisi otomatis oleh Railway (default 8080)
  MCP_SECRET  segmen path rahasia. Endpoint jadi /mcp/<MCP_SECRET>.
              Kalau kosong, endpoint jatuh ke /mcp - JANGAN dipakai di publik.
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

# --- pasang mesin cari upstream ke sys.path ---------------------------------
# core.py / design_system.py memang didesain diimpor flat (lihat scripts/search.py)
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "src" / "ui-ux-pro-max" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from core import (  # noqa: E402
    AVAILABLE_STACKS,
    CSV_CONFIG,
    MAX_RESULTS,
)
from core import search as _search  # noqa: E402
from core import search_stack as _search_stack  # noqa: E402

# design_system.py besar & opsional - kegagalan impor jangan sampai mematikan
# seluruh server; tool lain tetap harus jalan.
try:
    from design_system import generate_design_system as _generate_design_system  # noqa: E402

    _DS_ERROR = ""
except Exception as exc:  # pragma: no cover
    _generate_design_system = None
    _DS_ERROR = f"{type(exc).__name__}: {exc}"

AVAILABLE_DOMAINS = list(CSV_CONFIG.keys())

MCP_SECRET = os.environ.get("MCP_SECRET", "").strip().strip("/")
MCP_PATH = f"/mcp/{MCP_SECRET}" if MCP_SECRET else "/mcp"

INSTRUCTIONS = (
    "Design intelligence for building user interfaces. Call ui_search before "
    "choosing colors, fonts, layout patterns or chart types so the design is "
    "grounded in a curated database instead of guesswork. Call "
    "ui_stack_guidelines when writing code for a specific framework. Call "
    "ui_design_system when starting a new product and a full, coherent design "
    "system is needed in one shot."
)

mcp = FastMCP(
    "ui-ux-pro-max",
    instructions=INSTRUCTIONS,
    stateless_http=True,
    streamable_http_path=MCP_PATH,
)


def _clamp(n: Any, lo: int = 1, hi: int = 10) -> int:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return MAX_RESULTS
    return max(lo, min(hi, n))


@mcp.tool()
def ui_search(
    query: str,
    domain: Optional[str] = None,
    max_results: int = MAX_RESULTS,
) -> dict:
    """Search a curated UI/UX design database (BM25 ranked).

    Use this before picking colors, typography, layout or charts for any
    interface, so choices come from real design data instead of defaults.

    Args:
        query: Plain-language description, e.g. "dark fintech dashboard",
            "warm palette for a health app", "font pairing for editorial site".
        domain: Optional. One of: style (84 UI styles + AI prompt and CSS
            keywords), color (161 semantic palettes with full token sets),
            typography (73 font pairings with Google Fonts imports and Tailwind
            config), google-fonts (searchable font family index), icons, chart
            (25 chart types with library and a11y guidance), landing (page
            structure and CTA strategy), product (per-product-type style
            recommendations), ux (99 usability and accessibility guidelines
            with do/don't code), react (React performance rules), web (general
            web interface rules). Omit to auto-detect from the query.
        max_results: 1-10. Default 3.

    Returns:
        dict with domain, query, count and a list of matching rows.
    """
    if domain:
        domain = domain.strip().lower()
        if domain not in AVAILABLE_DOMAINS:
            return {
                "error": f"Unknown domain '{domain}'.",
                "available_domains": AVAILABLE_DOMAINS,
            }
    return _search(query, domain, _clamp(max_results))


@mcp.tool()
def ui_stack_guidelines(
    query: str,
    stack: str,
    max_results: int = MAX_RESULTS,
) -> dict:
    """Get framework-specific UI implementation guidelines with code examples.

    Each result carries a guideline, a description, an explicit do and don't,
    good and bad code samples, a severity level and a docs URL.

    Args:
        query: What is being built, e.g. "accessible modal", "list performance",
            "form validation".
        stack: One of react, nextjs, vue, svelte, astro, swiftui, react-native,
            flutter, nuxtjs, nuxt-ui, html-tailwind, shadcn, jetpack-compose,
            threejs, angular, laravel, javafx, wpf, winui, avalonia, uno, uwp.
        max_results: 1-10. Default 3.

    Returns:
        dict with stack, query, count and a list of guideline rows.
    """
    stack = (stack or "").strip().lower()
    if stack not in AVAILABLE_STACKS:
        return {
            "error": f"Unknown stack '{stack}'.",
            "available_stacks": AVAILABLE_STACKS,
        }
    return _search_stack(query, stack, _clamp(max_results))


@mcp.tool()
def ui_design_system(
    query: str,
    project_name: Optional[str] = None,
    output_format: str = "markdown",
) -> str:
    """Generate a complete, coherent design system for a product in one call.

    Combines style, colour tokens, typography and layout recommendations into a
    single specification. Use at the start of a new interface rather than
    assembling several ui_search calls by hand.

    Args:
        query: Product description, e.g. "personal health tracking PWA for iPad".
        project_name: Optional label used in the output heading.
        output_format: "markdown" (default) or "ascii".

    Returns:
        The design system as text. Nothing is written to disk.
    """
    if _generate_design_system is None:
        return f"design_system module unavailable on this server ({_DS_ERROR})"
    if output_format not in ("markdown", "ascii"):
        output_format = "markdown"
    return _generate_design_system(
        query,
        project_name,
        output_format,
        persist=False,
        page=None,
        output_dir=None,
    )


@mcp.tool()
def ui_capabilities() -> dict:
    """List every searchable domain and tech stack this server exposes.

    Call once when unsure which domain or stack value to pass to the other
    tools.
    """
    return {
        "domains": AVAILABLE_DOMAINS,
        "stacks": AVAILABLE_STACKS,
        "design_system_available": _generate_design_system is not None,
        "design_system_error": _DS_ERROR or None,
    }


# --- HTTP app ---------------------------------------------------------------
async def health(_request):
    """Cek cepat lewat browser: harus balas ok=true."""
    return JSONResponse(
        {
            "ok": True,
            "service": "ui-ux-pro-max-mcp",
            "mcp_path": "/mcp/<secret>" if MCP_SECRET else "/mcp",
            "secret_configured": bool(MCP_SECRET),
            "domains": len(AVAILABLE_DOMAINS),
            "stacks": len(AVAILABLE_STACKS),
            "design_system_available": _generate_design_system is not None,
        }
    )


@asynccontextmanager
async def lifespan(_app):
    async with mcp.session_manager.run():
        yield


app = Starlette(
    routes=[
        Route("/", health),
        Route("/healthz", health),
        Mount("/", app=mcp.streamable_http_app()),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )

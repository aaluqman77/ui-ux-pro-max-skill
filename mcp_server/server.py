#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UI/UX Pro Max - remote MCP server (Streamable HTTP).

Membungkus mesin cari BM25 di ``src/ui-ux-pro-max/scripts/`` jadi tool MCP yang
bisa dipanggil dari Claude lewat Settings > Connectors. Tanpa state, tanpa data
pengguna, tanpa tulis ke disk - murni query masuk, hasil ranking keluar.

Env:
  PORT        diisi otomatis oleh Railway (default 8080)
  MCP_SECRET  segmen path rahasia. Endpoint jadi /mcp/<MCP_SECRET>.
              Kalau kosong, endpoint jatuh ke /mcp - JANGAN dipakai di publik.
  LOG_LEVEL   default "info"
  HOST        alamat bind. Default 0.0.0.0 (wajib di belakang proxy Railway).
  MCP_ALLOWED_HOSTS
              opsional, dipisah koma. Kalau diisi, proteksi DNS rebinding
              dinyalakan dan cuma Host header ini yang diterima.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse

# --- pasang mesin cari upstream ke sys.path ---------------------------------
# core.py / design_system.py memang didesain diimpor flat (lihat scripts/search.py)
ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "src" / "ui-ux-pro-max" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from core import AVAILABLE_STACKS, CSV_CONFIG, MAX_RESULTS  # noqa: E402
from core import search as _search  # noqa: E402
from core import search_stack as _search_stack  # noqa: E402

# design_system.py besar & opsional - kegagalan impor jangan sampai mematikan
# seluruh server; tiga tool lainnya harus tetap jalan.
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

mcp = MCPServer("ui-ux-pro-max", instructions=INSTRUCTIONS, version="1.0.0")


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
        domain: Optional. One of: style (84 UI styles with AI prompt and CSS
            keywords), color (semantic palettes with full token sets),
            typography (font pairings with Google Fonts imports and Tailwind
            config), google-fonts (font family index), icons, chart (chart
            types with library and accessibility guidance), landing (page
            structure and CTA strategy), product (per-product-type style
            recommendations), ux (usability and accessibility guidelines with
            do/don't code), react (React performance rules), web (general web
            interface rules). Omit to auto-detect from the query.
        max_results: 1-10. Default 3.

    Returns:
        Matching rows plus the domain that was searched.
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
        Matching guideline rows for that stack.
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


# --- konfigurasi transport ---------------------------------------------------
# Proteksi DNS rebinding milik SDK memvalidasi Host header terhadap daftar
# putih. SDK menyalakannya OTOMATIS kalau host = 127.0.0.1/localhost/::1, dan
# daftar putihnya localhost saja -> di belakang proxy Railway setiap request
# balas 421 "Invalid Host header". Karena itu host diambil dari env (0.0.0.0)
# dan settings-nya diisi eksplisit, bukan dibiarkan None.
#
# Default: proteksi MATI. Alasannya proteksi ini dirancang buat server yang
# nempel di localhost dan bisa dijebak lewat browser; server ini publik, di
# balik HTTPS, dan sudah dijaga segmen path rahasia 48 hex. Isi
# MCP_ALLOWED_HOSTS kalau mau menyalakannya lagi.
_allowed = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
TRANSPORT_SECURITY = TransportSecuritySettings(
    enable_dns_rebinding_protection=bool(_allowed),
    allowed_hosts=_allowed,
    allowed_origins=[f"https://{h}" for h in _allowed],
)

BIND_HOST = os.environ.get("HOST", "0.0.0.0")


# --- health check ------------------------------------------------------------
def _health_payload() -> dict:
    return {
        "ok": True,
        "service": "ui-ux-pro-max-mcp",
        "mcp_path": "/mcp/<secret>" if MCP_SECRET else "/mcp",
        "secret_configured": bool(MCP_SECRET),
        "host_check": bool(_allowed),
        "domains": len(AVAILABLE_DOMAINS),
        "stacks": len(AVAILABLE_STACKS),
        "design_system_available": _generate_design_system is not None,
    }


@mcp.custom_route("/", methods=["GET"])
async def root(_request):
    return JSONResponse(_health_payload())


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_request):
    return JSONResponse(_health_payload())


# stateless_http=True: tiap request berdiri sendiri, aman kalau Railway
# menjalankan lebih dari satu instance dan tahan terhadap cold start.
app = mcp.streamable_http_app(
    streamable_http_path=MCP_PATH,
    stateless_http=True,
    transport_security=TRANSPORT_SECURITY,
    host=BIND_HOST,
)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=BIND_HOST,
        port=int(os.environ.get("PORT", "8080")),
        log_level=os.environ.get("LOG_LEVEL", "info"),
    )

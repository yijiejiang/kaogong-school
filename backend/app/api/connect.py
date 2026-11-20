"""LAN connection helpers and a QR code for the iOS client."""

import ipaddress
import socket
import subprocess
import sys
from io import BytesIO
from urllib.parse import quote

import qrcode
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.config import get_settings

router = APIRouter(prefix="/api/connect", tags=["connect"])


def _score(ip: str) -> int:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return 4
    if address.is_private:
        return 0
    if address.is_loopback or address.is_link_local:
        return 4
    if ip.startswith("198.18."):
        return 3
    return 2


def _macos_ips() -> list[str]:
    if sys.platform != "darwin":
        return []
    found: list[str] = []
    for interface in ("en0", "en1"):
        try:
            result = subprocess.run(
                ["ipconfig", "getifaddr", interface],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        ip = result.stdout.strip()
        if ip and ip not in found:
            found.append(ip)
    return found


def _lan_ips() -> list[str]:
    ips: list[str] = _macos_ips()
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        ip = probe.getsockname()[0]
        probe.close()
        if ip not in ips:
            ips.append(ip)
    except OSError:
        pass

    try:
        for item in socket.getaddrinfo(
            socket.gethostname(), None, socket.AF_INET
        ):
            ip = item[4][0]
            if ip not in ips:
                ips.append(ip)
    except socket.gaierror:
        pass

    usable = [
        ip
        for ip in ips
        if not ip.startswith(("127.", "169.254."))
    ]
    usable.sort(key=_score)
    return usable or ["127.0.0.1"]


def _base_url(request: Request, override: str = "") -> tuple[str, str]:
    if override.startswith(("http://", "https://")):
        return override.rstrip("/"), "custom"
    public = get_settings().public_base_url.strip()
    if public.startswith(("http://", "https://")):
        return public.rstrip("/"), "public"
    port = request.url.port or 8000
    return f"http://{_lan_ips()[0]}:{port}", "lan"


def _payload(base: str) -> str:
    return f"kaogong://connect?base={quote(base, safe='')}"


@router.get("/info")
async def connect_info(request: Request) -> dict:
    base, source = _base_url(request)
    return {
        "api_base": base,
        "source": source,
        "port": request.url.port or 8000,
        "ips": _lan_ips(),
        "payload": _payload(base),
    }


@router.get("/qr.png")
async def connect_qr(request: Request, base: str = "") -> Response:
    target, _source = _base_url(request, base)
    image = qrcode.make(_payload(target))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
    )

"""Outbound HTTP transport shared by the API and habit tracker workers."""

import inspect
import os

import httpx


def outbound_client(*, timeout: float) -> httpx.AsyncClient:
    proxy = os.getenv("OUTBOUND_PROXY_URL", "").strip()
    options = {"timeout": timeout}
    if proxy:
        # The deployed bot uses HTTPX 0.25; newer installations renamed this option.
        proxy_option = "proxy" if "proxy" in inspect.signature(httpx.AsyncClient).parameters else "proxies"
        options[proxy_option] = proxy
    return httpx.AsyncClient(**options)

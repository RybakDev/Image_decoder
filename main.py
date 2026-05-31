from io import BytesIO
from urllib.parse import urlparse
import ipaddress
import os
import socket
import requests
from fastapi import FastAPI, HTTPException
from PIL import Image

app = FastAPI()

MAX_OUTPUT_SIZE = int(os.getenv("MAX_OUTPUT_SIZE", "750"))
MAX_DOWNLOAD_BYTES = int(os.getenv("MAX_DOWNLOAD_BYTES", "20000000"))


def validate_url(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise HTTPException(400, "Invalid image URL")

    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                raise HTTPException(400, "Private URLs are not allowed")
    except socket.gaierror:
        raise HTTPException(400, "Could not resolve hostname")

@app.get("/")
def health():
    return {"status": "ok"}

@app.get("/pixels")
def pixels(url: str, size: int = 32):
    if not 1 <= size <= MAX_OUTPUT_SIZE:
        raise HTTPException(400, f"Size must be between 1 and {MAX_OUTPUT_SIZE}")

    validate_url(url)

    try:
        with requests.get(url, timeout=10, stream=True) as response:
            response.raise_for_status()

            content_length = response.headers.get("content-length")
            if content_length and content_length.isdigit() and int(content_length) > MAX_DOWNLOAD_BYTES:
                raise HTTPException(400, "Image download is too large")

            content = response.raw.read(MAX_DOWNLOAD_BYTES + 1)
            if len(content) > MAX_DOWNLOAD_BYTES:
                raise HTTPException(400, "Image download is too large")
    except requests.RequestException:
        raise HTTPException(400, "Could not download image")

    try:
        image = Image.open(BytesIO(content))
        image.thumbnail((size, size))
        image = image.convert("RGBA")
    except Exception:
        raise HTTPException(400, "Unsupported image")

    return {
        "width": image.width,
        "height": image.height,
        "pixels": [
            {"x": x, "y": y, "r": r, "g": g, "b": b, "a": a}
            for index, (r, g, b, a) in enumerate(image.getdata())
            for y, x in [divmod(index, image.width)]
        ],
    }

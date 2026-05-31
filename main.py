from io import BytesIO
from urllib.parse import urlparse
import socket
import ipaddress
import requests
from fastapi import FastAPI, HTTPException
from PIL import Image

app = FastAPI()

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
    if not 1 <= size <= 128:
        raise HTTPException(400, "Size must be between 1 and 128")

    validate_url(url)

    response = requests.get(url, timeout=5, stream=True)
    response.raise_for_status()

    content = response.raw.read(5_000_001)
    if len(content) > 5_000_000:
        raise HTTPException(400, "Image is too large")

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
            for y in range(image.height)
            for x in range(image.width)
            for r, g, b, a in [image.getpixel((x, y))]
        ],
    }
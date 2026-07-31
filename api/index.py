"""Entrypoint do Vercel.

O Vercel detecta o FastAPI aqui (api/index.py) e o executa como uma unica
Function. O app real vive em backend/app.py.
"""
import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"),
)

from app import app  # noqa: E402

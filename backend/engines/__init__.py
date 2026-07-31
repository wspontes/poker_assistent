"""Factory de motores. Troque o motor via env MOTOR_RECONHECIMENTO
(ou via query param ?motor=gemini|anthropic|mock no endpoint).
"""
import os

from .base import EngineBase
from .mock_engine import MockEngine

MOTORES_DISPONIVEIS = {
    MockEngine.nome: MockEngine,
}

try:
    from .anthropic_engine import AnthropicEngine

    MOTORES_DISPONIVEIS[AnthropicEngine.nome] = AnthropicEngine
except ImportError:  # pacote anthropic nao instalado
    pass

try:
    from .gemini_engine import GeminiEngine

    MOTORES_DISPONIVEIS[GeminiEngine.nome] = GeminiEngine
except ImportError:  # pacote google-genai nao instalado
    pass


def obter_motor(nome: str | None = None) -> EngineBase:
    nome = nome or os.getenv("MOTOR_RECONHECIMENTO", "gemini")
    if nome not in MOTORES_DISPONIVEIS:
        raise ValueError(
            f"Motor '{nome}' nao existe. Disponiveis: {', '.join(MOTORES_DISPONIVEIS)}"
        )
    return MOTORES_DISPONIVEIS[nome]()

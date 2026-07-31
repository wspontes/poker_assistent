"""Motor de mentira para testar o pipeline completo sem API key.

Devolve um resultado de exemplo realista, para validar frontend,
formato do JSON e modo debug antes de plugar um motor de verdade.
"""
from .base import EngineBase, normalizar_resposta

RESPOSTA_EXEMPLO = {
    "mesa": {
        "blinds": {"small_blind": 100, "big_blind": 200},
        "pote": 1500,
        "cartas_comunitarias": ["Kh", "9d", "2c"],
    },
    "jogadores": [
        {
            "nome": "wspontes",
            "stack": 4200,
            "posicao": "BTN",
            "cartas": ["Ah", "Kd"],
            "ativo": True,
            "aposta_atual": 0,
            "eh_jogador_principal": True,
            "confianca": "alta",
        },
        {
            "nome": "villain23",
            "stack": 3100,
            "posicao": "SB",
            "cartas": None,
            "ativo": True,
            "aposta_atual": 100,
            "eh_jogador_principal": False,
            "confianca": "media",
        },
        {
            "nome": "mttGrinder",
            "stack": 8900,
            "posicao": "BB",
            "cartas": None,
            "ativo": True,
            "aposta_atual": 200,
            "eh_jogador_principal": False,
            "confianca": "media",
        },
        {
            "nome": None,
            "stack": None,
            "posicao": "UTG",
            "cartas": None,
            "ativo": None,
            "aposta_atual": 0,
            "eh_jogador_principal": False,
            "confianca": "baixa",
        },
    ],
    "confianca_geral": "media",
    "observacoes": (
        "Motor mock (sem IA). Stack do jogador na posição UTG não "
        "foi possível ler com clareza."
    ),
    "motor": "mock",
}


class MockEngine(EngineBase):
    nome = "mock"

    def reconhecer(self, imagem_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
        return normalizar_resposta(RESPOSTA_EXEMPLO)

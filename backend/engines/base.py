"""Contrato base para os motores de reconhecimento.

Cada motor implementa `reconhecer` e retorna um dicionario no formato
normalizado (mesmo schema usado no endpoint). Isso permite trocar o
motor (Claude, OCR tradicional, etc.) sem mexer na API.
"""
import json
import re
from abc import ABC, abstractmethod

NAIPES = set("shdc")
RANKS = set("23456789tjqka")


def extrair_json(texto: str) -> dict:
    """Extrai o primeiro objeto JSON de um texto (ignora marcacoes de bloco)."""
    texto = texto.strip()
    if texto.startswith("```"):
        texto = re.sub(r"^```(?:json)?\s*", "", texto, flags=re.IGNORECASE)
        texto = re.sub(r"\s*```$", "", texto)
    inicio = texto.find("{")
    fim = texto.rfind("}")
    if inicio == -1 or fim == -1 or fim <= inicio:
        raise ValueError(f"Nao foi possivel extrair JSON da resposta: {texto[:200]}")
    return json.loads(texto[inicio : fim + 1])


def _para_numero(valor):
    """Converte '4.200', 'R$ 4.200,00', '4200', '1,5k' em int/float (ou None)."""
    if valor is None:
        return None
    if isinstance(valor, bool):
        return int(valor) if valor else 0
    if isinstance(valor, (int, float)):
        return valor
    if not isinstance(valor, str):
        return None

    texto = valor.strip().replace("R$", "").replace("$", "").strip()
    texto = texto.replace(" ", "").replace("\u00a0", "")
    multiplicador = 1.0
    if texto.lower().endswith("k"):
        multiplicador = 1000.0
        texto = texto[:-1]
    elif texto.lower().endswith("m"):
        multiplicador = 1_000_000.0
        texto = texto[:-1]

    texto = texto.replace(".", "").replace(",", ".") if "," in texto or "." in texto else texto
    try:
        valor_final = float(texto)
    except ValueError:
        return None
    return int(valor_final * multiplicador) if float(valor_final * multiplicador).is_integer() else valor_final * multiplicador


def _para_carta(valor):
    """Valida e normaliza uma carta tipo 'Ah' ou '10d'. Retorna None se invalida."""
    if not isinstance(valor, str):
        return None
    carta = valor.strip().lower().replace("10", "t")
    if len(carta) == 2 and carta[0] in RANKS and carta[1] in NAIPES:
        return carta[0].upper() + carta[1]
    return None


def _para_cartas(lista):
    if not isinstance(lista, list) or not lista:
        return None
    cartas = [_para_carta(c) for c in lista]
    if any(c is None for c in cartas):
        return None
    return cartas


def _para_boolean(valor):
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, str):
        return valor.strip().lower() in ("true", "sim", "ativo", "yes", "1")
    if isinstance(valor, (int, float)):
        return bool(valor)
    return None


def normalizar_resposta(raw: dict) -> dict:
    """Normaliza a resposta crua do motor para o schema padrao do endpoint."""
    mesa_raw = raw.get("mesa") if isinstance(raw.get("mesa"), dict) else {}
    blinds_raw = mesa_raw.get("blinds") if isinstance(mesa_raw.get("blinds"), dict) else {}

    jogadores = []
    for j in raw.get("jogadores", []):
        if not isinstance(j, dict):
            continue
        jogadores.append({
            "nome": j.get("nome"),
            "stack": _para_numero(j.get("stack")),
            "posicao": j.get("posicao"),
            "cartas": _para_cartas(j.get("cartas")),
            "ativo": _para_boolean(j.get("ativo")),
            "aposta_atual": _para_numero(j.get("aposta_atual")) or 0,
            "eh_jogador_principal": _para_boolean(j.get("eh_jogador_principal")) or False,
            "confianca": j.get("confianca"),
        })

    return {
        "mesa": {
            "blinds": {
                "small_blind": _para_numero(blinds_raw.get("small_blind")),
                "big_blind": _para_numero(blinds_raw.get("big_blind")),
            },
            "pote": _para_numero(mesa_raw.get("pote")),
            "cartas_comunitarias": _para_cartas(mesa_raw.get("cartas_comunitarias")),
        },
        "jogadores": jogadores,
        "observacoes": raw.get("observacoes"),
        "confianca_geral": raw.get("confianca_geral"),
        "motor": raw.get("motor"),
        "modelo_utilizado": raw.get("modelo_utilizado"),
    }


class EngineBase(ABC):
    nome: str = "base"

    @abstractmethod
    def reconhecer(self, imagem_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
        """Recebe a imagem bruta e devolve o JSON normalizado da mesa."""
        raise NotImplementedError

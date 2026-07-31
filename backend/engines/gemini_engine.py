"""Motor de reconhecimento usando a API gratuita do Google Gemini.

Usa o SDK google-genai. Envia a foto (bytes) + instrucoes e pede
resposta em JSON estruturado (response_mime_type="application/json").
Troque o modelo via env GEMINI_MODEL.
"""
import os

from google import genai
from google.genai import types as gtypes

from .base import EngineBase, extrair_json, normalizar_resposta

PROMPT_SISTEMA = """
Você é um sistema de reconhecimento de mesa de poker. Recebe uma foto
tirada de celular da tela do cliente GG Poker (GGPoker) rodando em um
PC. Sua única tarefa é extrair os dados visíveis e devolver APENAS um
JSON válido, sem texto fora dele.

ORIENTAÇÃO DE LAYOUT (GG Poker):
- A mesa é oval; o herói (dono da conta logada) fica no assento
  inferior central, com as próprias cartas viradas para cima à sua frente.
- Cada assento ocupado mostra: nome do usuário (pode vir abreviado,
  ex: "wspont", "Villain23") acima do avatar; o número de fichas
  (stack) abaixo do avatar, num painel colorido.
- As apostas da rodada aparecem em círculos/bets na área central, à
  frente de cada jogador.
- O botão do dealer é um disco branco pequeno sobre a mesa.
- Os blinds aparecem no topo da tela (ex: "100/200").
- O pote aparece no centro da mesa, acima das cartas comunitárias.
- As cartas comunitárias ficam no centro.

REGRAS DE EXTRAÇÃO:
- COPIE EXATAMENTE o que está visível. Não invente, não complete,
  não adivinhe com base em conhecimento de poker.
- Só liste assentos que estão de fato ocupados e legíveis.
- Não confunda nome do torneio, nome da mesa ou textos de publicidade
  com nome de jogador.
- Use null para qualquer campo que não conseguir ler com certeza.
- "stack", "pote" e blinds devem ser números (inteiros) já limpos,
  ignorando separadores (ex: "4,200" -> 4200, "R$ 1.500" -> 1500).
- "cartas" e "cartas_comunitarias": arrays de strings RankNaipe,
  ex: ["Ah", "Kd"]. O 10 é representado como "T".

NAIPES POR COR (CRÍTICO — o GG Poker usa CORES, não símbolos, para
diferenciar naipes; símbolos podem ficar borrados na foto):
- Carta VERMELHA = copas -> sufixo "h" (ex: "Ah" = ás de copas)
- Carta AZUL = ouros -> sufixo "d" (ex: "Kd" = rei de ouros)
- Carta VERDE = paus -> sufixo "c" (ex: "9c" = nove de paus)
- Carta PRETA = espadas -> sufixo "s" (ex: "Ks" = rei de espadas)
Identifique o naipe pela COR dominante do corpo da carta (o desenho
central), não pelo símbolo (que pode estar pequeno/borrado).
- "posicao": calcule a partir do botão do dealer. O primeiro jogador à
  esquerda do botão é o SB, o segundo o BB, e então UTG/MP/CO/BTN
  conforme o número de jogadores e a posição visual na mesa. Use BTN,
  SB, BB, UTG, MP, CO ou null se não der para determinar.
- "ativo": true se o jogador ainda está na mão, false se já deu fold
  (cartas/fichas viradas ou ausência de ação), null se não der para dizer.
- "aposta_atual": fichas que o jogador tem apostadas na rodada atual
  (0 se nada).
- "eh_jogador_principal": true apenas para o herói (assento inferior
  central, com cartas viradas para cima).
- "confianca" por jogador: "alta", "media" ou "baixa".
- Preencha "observacoes" com o que não conseguiu ler ou dúvidas.
- Não invente dados que não estejam na imagem.
"""

SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "mesa": {
            "type": "OBJECT",
            "properties": {
                "blinds": {
                    "type": "OBJECT",
                    "properties": {
                        "small_blind": {"type": "INTEGER", "nullable": True},
                        "big_blind": {"type": "INTEGER", "nullable": True},
                    },
                },
                "pote": {"type": "INTEGER", "nullable": True},
                "cartas_comunitarias": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "nullable": True,
                },
            },
        },
        "jogadores": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "nome": {"type": "STRING", "nullable": True},
                    "stack": {"type": "INTEGER", "nullable": True},
                    "posicao": {"type": "STRING", "nullable": True},
                    "cartas": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "nullable": True,
                    },
                    "ativo": {"type": "BOOLEAN", "nullable": True},
                    "aposta_atual": {"type": "INTEGER", "nullable": True},
                    "eh_jogador_principal": {"type": "BOOLEAN", "nullable": True},
                    "confianca": {"type": "STRING", "nullable": True},
                },
            },
        },
        "confianca_geral": {"type": "STRING", "nullable": True},
        "observacoes": {"type": "STRING", "nullable": True},
    },
}


class GeminiEngine(EngineBase):
    nome = "gemini"

    MODELO_PADRAO = "gemini-3.6-flash"
    MODELOS_FALLBACK = [
        "gemini-3.1-flash-lite",
        "gemini-flash-latest",
        "gemini-2.5-flash-lite",
    ]

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY nao configurada. Defina no arquivo .env.")
        self._client = genai.Client(api_key=api_key)

    def _tentar_modelo(self, modelo, imagem_bytes, mime_type):
        imagem = gtypes.Part.from_bytes(data=imagem_bytes, mime_type=mime_type)
        return self._client.models.generate_content(
            model=modelo,
            contents=[
                imagem,
                "Extraia os dados desta mesa de poker (GG Poker) e devolva o JSON.",
            ],
            config=gtypes.GenerateContentConfig(
                system_instruction=PROMPT_SISTEMA,
                temperature=0,
                response_mime_type="application/json",
                response_schema=SCHEMA,
            ),
        )

    def reconhecer(self, imagem_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
        modelo = os.getenv("GEMINI_MODEL", self.MODELO_PADRAO)
        tentativas = [modelo] + [m for m in self.MODELOS_FALLBACK if m != modelo]

        resposta = None
        modelo_utilizado = modelo
        ultimo_erro = None
        for cand in tentativas:
            try:
                resposta = self._tentar_modelo(cand, imagem_bytes, mime_type)
                modelo_utilizado = cand
                break
            except Exception as exc:  # noqa: BLE001
                ultimo_erro = exc
        if resposta is None:
            raise RuntimeError(f"Falha ao chamar Gemini: {ultimo_erro}")

        try:
            raw = extrair_json(resposta.text or "")
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Falha ao interpretar resposta do Gemini: {exc}") from exc

        raw.setdefault("motor", self.nome)
        raw["modelo_utilizado"] = modelo_utilizado
        return normalizar_resposta(raw)

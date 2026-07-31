"""Motor de reconhecimento usando a API da Anthropic (Claude).

Envia a foto em base64 para um modelo multimodal e pede retorno
estruturado em JSON. Troque o modelo via env ANTHROPIC_MODEL.
"""
import base64
import json
import os

import anthropic

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

Formato exato esperado:
{
  "mesa": {
    "blinds": { "small_blind": 100, "big_blind": 200 },
    "pote": 1500,
    "cartas_comunitarias": ["Kh", "9d", "2c"]
  },
  "jogadores": [
    {
      "nome": "wspontes",
      "stack": 4200,
      "posicao": "BTN",
      "cartas": ["Ah", "Kd"],
      "ativo": true,
      "aposta_atual": 0,
      "eh_jogador_principal": true,
      "confianca": "alta"
    }
  ],
  "confianca_geral": "media",
  "observacoes": "Stack do jogador na posição UTG não foi possível ler com clareza."
}
"""


class AnthropicEngine(EngineBase):
    nome = "anthropic"

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY nao configurada. Defina no arquivo .env.")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._modelo = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    def reconhecer(self, imagem_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
        b64 = base64.b64encode(imagem_bytes).decode("ascii")
        resposta = self._client.messages.create(
            model=self._modelo,
            max_tokens=3000,
            temperature=0,
            system=PROMPT_SISTEMA,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Extraia os dados desta mesa de poker e devolva o JSON.",
                        },
                    ],
                }
            ],
        )
        texto = "".join(b.text for b in resposta.content if getattr(b, "type", "") == "text")
        try:
            raw = extrair_json(texto)
        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Falha ao interpretar resposta do Claude: {exc}") from exc

        raw.setdefault("motor", self.nome)
        return normalizar_resposta(raw)

# Poker Foto Reconhecimento — Protótipo

Protótipo para validar a extração de dados de uma mesa de poker a partir
de **foto tirada de celular** (ângulo, reflexo, iluminação variável), usando
um modelo de visão multimodal em vez de OCR tradicional.

Reconhecimento real **gratuito** via API do **Google Gemini** (free tier) ou,
opcionalmente, Claude/Anthropic. Arquitetura modular para trocar de motor.

Este protótipo **não** tem lógica de decisão (ICM, equity, push/fold). É só
reconhecimento + retorno em JSON.

## O que faz

1. Você abre a página pelo celular (mesma rede Wi-Fi do PC).
2. Tira/escoee uma foto da mesa de poker exibida no monitor.
3. Envia para a API.
4. Recebe JSON com: blinds, pote, cartas comunitárias e, por jogador,
   nome, stack, posição, cartas, ativo/fold, aposta atual — com campos de
   confiança e observações para o que não foi lido.

## Estrutura

```
poker-reconhecimento/
├── backend/
│   ├── app.py                 # API FastAPI (serve o frontend + /api/reconhecer)
│   ├── requirements.txt
│   ├── .env.example
│   └── engines/               # Motores de reconhecimento (troca modular)
│       ├── base.py            # Contrato + normalização do JSON
│       ├── gemini_engine.py   # Google Gemini (gratuito) — padrão
│       ├── anthropic_engine.py# Claude (opcional, pago)
│       └── mock_engine.py     # Mock para testar sem API key
├── frontend/                  # Página mobile (HTML/CSS/JS puro)
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── run.ps1                    # Subida rápida no Windows
└── README.md
```

## Como rodar (Windows)

### Opção A — script automático

```powershell
.\run.ps1
```

O script cria um venv, instala dependências, cria o `.env` a partir do
exemplo (se não existir) e sobe o servidor em `0.0.0.0:8000`, imprimindo
o endereço para acessar do celular.

### Opção B — manual

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env   # edite e preencha GEMINI_API_KEY
python app.py                 # ou: uvicorn app:app --host 0.0.0.0 --port 8000
```

## Reconhecimento gratuito com Google Gemini

1. Acesse <https://aistudio.google.com/apikey> com sua conta Google.
2. Clique em **Create API key** (é grátis; não pede cartão).
3. Copie a chave e cole em `backend\.env`:
   ```
   GEMINI_API_KEY=AIza...
   ```
4. Reinicie o servidor.

O free tier do Gemini tem limites de requisições por minuto/dia — mais
que suficiente para testar o protótipo. O modelo padrão é
`gemini-3.6-flash`; se um modelo estiver fora de cota/demanda alta, o
sistema tenta automaticamente modelos alternativos (`gemini-3.1-flash-lite`,
`gemini-flash-latest`, `gemini-2.5-flash-lite`) e reporta qual foi usado
no campo `modelo_utilizado`.

## Acessando do celular

1. PC e celular na **mesma rede Wi-Fi**.
2. Descubra o IP do PC: `ipconfig` → IPv4 (ex: `192.168.0.10`).
3. No celular, abra: `http://<IP_DO_PC>:8000`
4. Tire a foto e envie.

> Firewall do Windows pode pedir permissão para o Python — aceite para
> redes privadas.

## Instalação no celular (PWA)

O app é um PWA: tem `manifest.json`, service worker e ícones, então pode
ser **instalado no celular** (ícone na home screen, abre em tela cheia).

**Importante:** instalação de PWA (botão "Instalar" e service worker) só
funciona em contexto **HTTPS** ou `localhost`. Acessando por `http://192.168.x.x`
(rede local) o botão de instalar não aparece.

Opções para conseguir HTTPS:

1. **Túnel gratuito (mais rápido)** — expõe o servidor local por HTTPS:
   ```powershell
   winget install --id Cloudflare.cloudflared
   cloudflared tunnel --url http://localhost:8000
   ```
   Ele imprime uma URL `https://<hash>.trycloudflare.com` — abra no
   celular e use o botão "Instalar app".

2. **Deploy do backend** em um host com HTTPS (Render, Railway, etc.) com
   `GEMINI_API_KEY` configurada como variável de ambiente — aí o PWA
   funciona para qualquer um, de qualquer rede.

3. **iOS (iPhone)**: mesmo sem HTTPS, no Safari use o menu Compartilhar →
   **"Adicionar à Tela de Início"** — o atalho abre em tela cheia graças
   às metas do PWA (sem service worker/offline).

> No iOS o botão "Instalar app" (Android) não aparece; use o caminho do
> Safari acima.

## Motores de reconhecimento

Selecionável na página ou via query param:

| Motor       | Como ativar                                          | Uso                                  |
|-------------|------------------------------------------------------|--------------------------------------|
| `gemini`    | `GEMINI_API_KEY` no `.env` (padrão)                  | Reconhecimento real, gratuito        |
| `anthropic` | `ANTHROPIC_API_KEY` no `.env`                        | Reconhecimento real, pago (opcional) |
| `mock`      | `?motor=mock` ou `MOTOR_RECONHECIMENTO=mock` no `.env` | Teste do pipeline sem API key      |

Sem chave configurada, o sistema cai automaticamente para o mock e avisa
no campo `observacoes` (importante: o mock devolve **dados falsos de
exemplo** — não é leitura real).

Para trocar o modelo: `GEMINI_MODEL=gemini-3.6-flash` ou
`ANTHROPIC_MODEL=claude-3-5-sonnet-latest` no `.env`.

## Endpoints

- `GET /` → página mobile.
- `GET /api/health` → status, motores disponíveis, chaves configuradas.
- `POST /api/reconhecer` → recebe `arquivo` (multipart) e devolve o JSON.
  - Query params opcionais: `motor=gemini|anthropic|mock`, `debug=true`.
  - `debug=true` inclui `tempo_ms` no retorno.

## Modo debug

Na página, ative **"Modo debug"** para ver a foto enviada ao lado do JSON
retornado (uma grade lado a lado), facilitando comparar o que o sistema
acertou/errou.

## Sugestão de ação (check/call/bet/fold/raise)

A resposta agora inclui um campo `acao_sugerida` com uma sugestão
determinística (grátis, sem IA extra) baseada em:

- **Força da mão**: tier pré-flop (par forte/médio, ás, conector,
  suited...) ou categoria pós-flop (par, dois pares, trinca, flush,
  sequência...) com contagem de outs para desenhos (flush draw, OESD).
- **Pot odds**: o quanto custa pagar vs. o tamanho do pote.
- **Situação**: se você enfrenta aposta, se pode dar check, ou se já
  igualou a aposta da rodada.

O `motivo` explica em português o raciocínio usado. É um heurístico de
estudo — não substitui análise completa de equity/ICM.

## Exemplo de resposta

```json
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
    },
    {
      "nome": "villain23",
      "stack": 3100,
      "posicao": "SB",
      "cartas": null,
      "ativo": true,
      "aposta_atual": 100,
      "eh_jogador_principal": false,
      "confianca": "media"
    }
  ],
  "confianca_geral": "media",
  "observacoes": "Stack do jogador na posição UTG não foi possível ler com clareza."
}
```

## Fora de escopo (por enquanto)

- Lógica de decisão, odds, equity, ICM.
- Autenticação, histórico de mãos, persistência.
- Múltiplas mesas simultâneas.

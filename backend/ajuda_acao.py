"""Sugestao de acao (check/call/bet/fold/raise) por regras deterministicas.

Recebe o JSON normalizado do reconhecimento e devolve um dicionario
"acao_sugerida" com base em: forca da mao (pre-flop / pos-flop),
pot odds para pagar e situacao do heroi na rodada.
"""
from collections import Counter
from itertools import combinations

RANKS = "23456789tjqka"
RANK_VAL = {r: i for i, r in enumerate(RANKS)}

CATEGORIA = {
    8: "sequência real/straight flush",
    7: "quadra",
    6: "full house",
    5: "flush",
    4: "sequência",
    3: "trinca",
    2: "dois pares",
    1: "um par",
    0: "carta alta",
}

EQUITY_POR_CATEGORIA = {
    8: 0.96, 7: 0.95, 6: 0.92, 5: 0.88, 4: 0.84,
    3: 0.78, 2: 0.68, 1: 0.58, 0: 0.42,
}


def _cartas_par(codigos):
    """Converte ['Ah', 'Kd'] -> [(12, 'h'), (11, 'd')]. None se invalido."""
    resultado = []
    for c in codigos:
        if not isinstance(c, str) or len(c) != 2 or c[0].lower() not in RANK_VAL or c[1] not in "shdc":
            return None
        resultado.append((RANK_VAL[c[0].lower()], c[1]))
    return resultado


def _score5(h5):
    vals = sorted((v for v, _ in h5), reverse=True)
    uniq = sorted(set(vals), reverse=True)
    is_flush = len({s for _, s in h5}) == 1
    is_straight = (len(uniq) == 5 and (uniq[0] - uniq[4] == 4)) or uniq == [12, 3, 2, 1, 0]
    alto = 3 if uniq == [12, 3, 2, 1, 0] else uniq[0]
    if is_flush and is_straight:
        return (8, alto, 0, 0, 0, 0)
    cont = Counter(vals)
    grupos = sorted(cont.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    qtd_top, rank_top = grupos[0][1], grupos[0][0]
    if qtd_top == 4:
        return (7, rank_top, grupos[1][0], 0, 0, 0)
    if qtd_top == 3 and len(grupos) > 1 and grupos[1][1] == 2:
        return (6, rank_top, grupos[1][0], 0, 0, 0)
    if is_flush:
        return (5, *vals, 0)
    if is_straight:
        return (4, alto, 0, 0, 0, 0)
    if qtd_top == 3:
        k = [v for v in vals if v != rank_top][:2]
        return (3, rank_top, k[0], k[1], 0, 0)
    pares = [g for g in grupos if g[1] == 2]
    if len(pares) == 2:
        hi, lo = pares[0][0], pares[1][0]
        k = next(v for v in vals if v not in (hi, lo))
        return (2, hi, lo, k, 0, 0)
    if qtd_top == 2:
        k = [v for v in vals if v != rank_top][:3]
        return (1, rank_top, k[0], k[1], k[2], 0)
    return (0, *vals, 0)


def melhor_mao(cartas):
    """Melhor pontuacao entre todas as combinacoes de 5 cartas."""
    melhor = None
    for comb in combinations(cartas, 5):
        score = _score5(comb)
        if melhor is None or score > melhor:
            melhor = score
    return melhor


def _outs_desenho(cartas):
    """Conta outs de flush draw e straight draw (aproximado)."""
    if len(cartas) < 4:
        return 0
    suits = Counter(s for _, s in cartas)
    naipes_4 = [n for n, q in suits.items() if q == 4]
    naipes_5 = [n for n, q in suits.items() if q == 5]
    outs = 9 if (naipes_4 and not naipes_5) else 0
    vals = {v for v, _ in cartas}
    if 12 in vals:
        vals.add(-1)  # as pode completar A-2-3-4-5
    faltantes = set()
    for h in range(3, 13):
        seq = {-1, 0, 1, 2, 3} if h == 3 else set(range(h - 4, h + 1))
        have = seq & vals
        if len(have) == 4:
            faltantes.add(next(iter(seq - have)))
    return min(outs + 4 * len(faltantes), 21)


def _preflop(cartas):
    """Retorna (equity_estimada, descricao) para duas cartas fechadas."""
    (r1, s1), (r2, s2) = cartas
    suited = s1 == s2
    hi, lo = max(r1, r2), min(r1, r2)
    if r1 == r2:
        if hi >= 10:
            return 0.62, f"Par forte ({RANKS[hi].upper()}{RANKS[hi].upper()})"
        if hi >= 6:
            return 0.52, f"Par médio ({RANKS[hi].upper()}{RANKS[hi].upper()})"
        return 0.42, f"Par baixo ({RANKS[hi].upper()}{RANKS[hi].upper()})"
    if hi == 12:
        if lo >= 10:
            return (0.58 if suited else 0.54), f"Ás forte ({RANKS[hi].upper()}{RANKS[lo].upper()}{'s' if suited else 'o'})"
        if suited:
            return 0.45, "Ás suited"
        return 0.38, "Ás fraco (offsuit)"
    if hi >= 10 and lo >= 9:
        return (0.54 if suited else 0.48), "Broadway (T-J-Q-K-A)"
    if hi >= 10:
        return (0.42 if suited else 0.36), "Conector broadway"
    if suited and hi - lo <= 2 and hi >= 7:
        return 0.42, "Conector suited"
    if suited and hi - lo <= 4:
        return 0.36, "Suited com gap"
    return 0.32, "Mão fraca"


def _equity_posflop(cartas_hero, board):
    """Estimativa de equity pos-flop: mao formada OU desenho (o maior)."""
    todas = cartas_hero + board
    score = melhor_mao(todas)
    equity = EQUITY_POR_CATEGORIA[score[0]]
    desc = CATEGORIA[score[0]]
    outs = _outs_desenho(todas)
    ruas = 2 if len(board) == 3 else 1 if len(board) == 4 else 0
    equity_desenho = 0.0
    if outs and ruas:
        equity_desenho = min(0.55, outs * 4 * (ruas / 2) / 100)
    if equity_desenho > equity:
        equity = equity_desenho
        desc = f"desenho com {outs} outs"
    return equity, desc, score


def _sem_informacao(motivo):
    return {"acao": "sem_informacao", "motivo": motivo}


def avaliar(resultado: dict) -> dict:
    mesa = resultado.get("mesa") or {}
    jogadores = resultado.get("jogadores") or []
    if not jogadores:
        return _sem_informacao("Nenhum jogador reconhecido na imagem.")

    heroi = next((j for j in jogadores if j.get("eh_jogador_principal")), None)
    if not heroi:
        return _sem_informacao("Jogador principal não identificado na imagem.")

    codigos_hero = heroi.get("cartas")
    if not codigos_hero or len(codigos_hero) < 2:
        return _sem_informacao("Cartas do jogador principal não foram lidas.")

    cartas_hero = _cartas_par(codigos_hero)
    if not cartas_hero:
        return _sem_informacao("Cartas do jogador principal inválidas.")

    board = mesa.get("cartas_comunitarias") or []
    board_par = _cartas_par(board) if board else []
    if board and not board_par:
        return _sem_informacao("Cartas comunitárias inválidas.")

    pote = mesa.get("pote") or 0
    blinds = mesa.get("blinds") or {}
    bb = blinds.get("big_blind") or 0
    hero_bet = heroi.get("aposta_atual") or 0
    outros_bets = [j.get("aposta_atual") or 0 for j in jogadores if j is not heroi]
    max_bet = max(outros_bets) if outros_bets else 0
    para_chamar = max(0, max_bet - hero_bet)

    if board_par:
        equity, desc, _score = _equity_posflop(cartas_hero, board_par)
    else:
        equity, desc = _preflop(cartas_hero)
        _score = None

    r = {"forca_mao": desc, "equity_estimada": round(equity, 2), "pot_odds": None}

    # 1) Heroi ja igualou/apostou o maximo da rodada
    if max_bet > 0 and hero_bet >= max_bet:
        if equity >= 0.8:
            r.update({
                "acao": "raise",
                "motivo": (f"Você já igualou a aposta e sua mão é forte ({desc}, "
                           f"equity ~{equity:.0%}). Aumentar pressiona seus adversários."),
            })
        else:
            r.update({
                "acao": "sem_acao",
                "motivo": ("Você já igualou a aposta desta rodada. A menos que seja seu "
                           f"turno para aumentar, aguarde. (Mão: {desc}, equity ~{equity:.0%}.)"),
            })
        return r

    # 2) Enfrenta aposta (max_bet > hero_bet)
    if para_chamar > 0:
        pote_total = pote + para_chamar
        pot_odds = (para_chamar / pote_total) if pote_total else 1.0
        r["pot_odds"] = round(pot_odds, 3)
        margem = equity - pot_odds
        if margem >= 0.15 or equity >= 0.75:
            r.update({
                "acao": "raise",
                "valor": max(bb, int(round(pote_total / bb) * bb)) if bb else pote_total,
                "motivo": (f"Sua mão é forte ({desc}, equity ~{equity:.0%}) contra "
                           f"{pot_odds:.0%} necessários para pagar {para_chamar}. "
                           "Há valor em aumentar."),
            })
        elif margem >= 0.02:
            r.update({
                "acao": "call",
                "valor": para_chamar,
                "motivo": (f"Pagar {para_chamar} é lucrativo: equity ~{equity:.0%} vs "
                           f"{pot_odds:.0%} de pot odds. Sua mão: {desc}."),
            })
        else:
            r.update({
                "acao": "fold",
                "motivo": (f"Pagar {para_chamar} pede {pot_odds:.0%} de pot odds e sua mão "
                           f"tem só ~{equity:.0%} ({desc}). Fold é o mais barato."),
            })
        return r

    # 3) Sem aposta a enfrentar: pode dar check ou apostar
    if equity >= 0.6:
        valor_bet = max(bb, int(round((pote * 0.66 or bb) / bb) * bb)) if bb else int(pote * 0.66) or 1
        r.update({
            "acao": "bet",
            "valor": valor_bet,
            "motivo": (f"Mão forte ({desc}, equity ~{equity:.0%}) sem aposta a enfrentar. "
                       "Apostar ~66% do pote protege e extrai valor."),
        })
    else:
        r.update({
            "acao": "check",
            "motivo": (f"Mão modesta ({desc}, equity ~{equity:.0%}) e ninguém apostou. "
                       "Dar check é a opção barata."),
        })
    return r

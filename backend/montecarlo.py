"""Equity de poker por Monte Carlo vetorizado (NumPy).

Compara a mao do heroi contra 1 oponente aleatorio, completando o board
sorteadamente, e devolve a fracao de vitorias (+ metade dos empates).
"""
import numpy as np
from itertools import combinations

RANKS = "23456789tjqka"
RANK_VAL = {r: i for i, r in enumerate(RANKS)}

DECK = [(r, s) for s in "shdc" for r in range(13)]

P4, P3, P2, P1, P0 = 13**4, 13**3, 13**2, 13, 1
BASE = 13**5

_COMB5 = np.array(list(combinations(range(7), 5)))  # (21, 5)


def _eval5(ranks, suits):
    """Score de 5 cartas, vetorizado. ranks/suits: (N, 5)."""
    n = ranks.shape[0]
    vals = np.sort(ranks, axis=1)[:, ::-1]
    mx, mn = vals[:, 0], vals[:, 4]

    is_flush = (suits == suits[:, :1]).all(axis=1)

    no_repeat = ~(vals[:, :-1] == vals[:, 1:]).any(axis=1)
    is_straight = no_repeat & (mx - mn == 4)
    wheel = (vals == np.array([12, 3, 2, 1, 0])).all(axis=1)
    is_straight |= wheel
    straight_high = np.where(wheel, 3, mx)

    cnt = np.zeros((n, 13), dtype=np.int8)
    for i in range(5):
        cnt[np.arange(n), ranks[:, i]] += 1
    has4 = (cnt == 4).any(axis=1)
    has3 = (cnt == 3).any(axis=1)
    npairs = (cnt == 2).sum(axis=1)
    pair_ranks = np.where((cnt == 2).any(axis=1), np.argmax(cnt == 2, axis=1), 0)

    sf = is_flush & is_straight
    qd = has4
    fh = has3 & (npairs == 1)
    tr = has3 & ~fh
    fl = is_flush & ~sf
    st = is_straight & ~sf
    tp = npairs == 2
    op = (npairs == 1) & ~(fh | qd | tr | fl | st | sf)
    hc = ~(sf | fl | st | qd | fh | tr | tp | op)

    score = np.zeros(n, dtype=np.int64)
    if sf.any():
        score[sf] = 8 * BASE + straight_high[sf].astype(np.int64) * P4
    if qd.any():
        quad_r = np.argmax(cnt == 4, axis=1)
        kick = np.where(vals == quad_r[:, None], -1, vals)
        k0 = np.max(kick, axis=1)
        score[qd] = 7 * BASE + quad_r[qd].astype(np.int64) * P4 + k0[qd].astype(np.int64) * P3
    if fh.any():
        trips_r = np.argmax(cnt == 3, axis=1)
        pair_r = np.argmax(cnt == 2, axis=1)
        score[fh] = 6 * BASE + trips_r[fh].astype(np.int64) * P4 + pair_r[fh].astype(np.int64) * P3
    if fl.any():
        score[fl] = 5 * BASE + (
            vals[fl, 0].astype(np.int64) * P4
            + vals[fl, 1].astype(np.int64) * P3
            + vals[fl, 2].astype(np.int64) * P2
            + vals[fl, 3].astype(np.int64) * P1
            + vals[fl, 4].astype(np.int64)
        )
    if st.any():
        score[st] = 4 * BASE + straight_high[st].astype(np.int64) * P4
    if tr.any():
        trips_r = np.argmax(cnt == 3, axis=1)
        kick = np.where(vals == trips_r[:, None], -1, vals)
        ks = np.sort(kick, axis=1)[:, ::-1]
        score[tr] = (
            3 * BASE
            + trips_r[tr].astype(np.int64) * P4
            + ks[tr, 0].astype(np.int64) * P3
            + ks[tr, 1].astype(np.int64) * P2
        )
    if tp.any():
        two = cnt == 2
        ranks_ar = np.arange(13)
        hi = np.max(np.where(two, ranks_ar, -1), axis=1)
        lo = np.max(np.where(two & (ranks_ar != hi[:, None]), ranks_ar, -1), axis=1)
        kick = np.where(vals == hi[:, None], -1, vals)
        kick = np.where(vals == lo[:, None], -1, kick)
        k0 = np.max(kick, axis=1)
        score[tp] = (
            2 * BASE
            + hi[tp].astype(np.int64) * P4
            + lo[tp].astype(np.int64) * P3
            + k0[tp].astype(np.int64) * P2
        )
    if op.any():
        pair_r = np.argmax(cnt == 2, axis=1)
        kick = np.where(vals == pair_r[:, None], -1, vals)
        ks = np.sort(kick, axis=1)[:, ::-1]
        score[op] = (
            1 * BASE
            + pair_r[op].astype(np.int64) * P4
            + ks[op, 0].astype(np.int64) * P3
            + ks[op, 1].astype(np.int64) * P2
            + ks[op, 2].astype(np.int64) * P1
        )
    if hc.any():
        score[hc] = (
            vals[hc, 0].astype(np.int64) * P4
            + vals[hc, 1].astype(np.int64) * P3
            + vals[hc, 2].astype(np.int64) * P2
            + vals[hc, 3].astype(np.int64) * P1
            + vals[hc, 4].astype(np.int64)
        )
    return score


def _eval7(ranks, suits):
    """Score de 7 cartas: maximo entre as 21 combinacoes de 5. ranks/suits: (N, 7)."""
    n = ranks.shape[0]
    r5 = ranks[:, _COMB5]  # (N, 21, 5)
    s5 = suits[:, _COMB5]
    sc = _eval5(r5.reshape(n * 21, 5), s5.reshape(n * 21, 5))
    return sc.reshape(n, 21).max(axis=1)


def equity(cartas_hero, board, n_hands=20000, rng=None):
    """Equity do heroi vs 1 oponente aleatorio (0..1).

    cartas_hero: lista de (rank 0-12, naipe 'shdc'), ex [(12,'h'),(11,'d')].
    board: mesma formato (pode ser vazio = pre-flop, ou 3/4/5 cartas).
    """
    rng = rng or np.random.default_rng()

    _SUIT_IDX = {"s": 0, "h": 1, "d": 2, "c": 3}
    hero_r = np.array([r for r, _ in cartas_hero], dtype=np.int8)
    hero_s = np.array([_SUIT_IDX[s] for _, s in cartas_hero], dtype=np.int8)
    known_r = np.array([r for r, _ in board], dtype=np.int8)
    known_s = np.array([_SUIT_IDX[s] for _, s in board], dtype=np.int8)
    k = len(board)

    usados = set(map(tuple, cartas_hero)) | set(map(tuple, board))
    deck = [c for c in DECK if c not in usados]
    deck_r = np.array([r for r, _ in deck], dtype=np.int8)
    deck_s = np.array([_SUIT_IDX[s] for _, s in deck], dtype=np.int8)
    m = len(deck)
    if m < 7:
        return 1.0

    perm = np.argsort(rng.random((n_hands, m)), axis=1)
    opp = perm[:, :2]
    fill = perm[:, 2 : 2 + (5 - k)]

    opp_r = deck_r[opp]
    opp_s = deck_s[opp]
    fill_r = deck_r[fill]
    fill_s = deck_s[fill]

    h_r = np.concatenate(
        [np.broadcast_to(hero_r, (n_hands, 2)), np.broadcast_to(known_r, (n_hands, k)), fill_r],
        axis=1,
    )
    h_s = np.concatenate(
        [np.broadcast_to(hero_s, (n_hands, 2)), np.broadcast_to(known_s, (n_hands, k)), fill_s],
        axis=1,
    )
    o_r = np.concatenate(
        [opp_r, np.broadcast_to(known_r, (n_hands, k)), fill_r], axis=1
    )
    o_s = np.concatenate(
        [opp_s, np.broadcast_to(known_s, (n_hands, k)), fill_s], axis=1
    )

    hs = _eval7(h_r, h_s)
    os = _eval7(o_r, o_s)
    wins = (hs > os).sum()
    ties = (hs == os).sum()
    return float((wins + 0.5 * ties) / n_hands)

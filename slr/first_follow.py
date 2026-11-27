"""Algoritmos FIRST e FOLLOW (Aho et al., seção 4.4.2)."""

from __future__ import annotations

from .gramatica import EPSILON, FIM, Gramatica


def calcular_first(g: Gramatica) -> dict[str, set[str]]:
    """FIRST de cada não terminal (pode conter & = ε). Ponto fixo sobre as produções."""
    first: dict[str, set[str]] = {nt: set() for nt in g.nao_terminais}
    mudou = True
    while mudou:
        mudou = False
        for p in g.producoes:
            novo = first_sequencia(p.corpo, first, g)
            if not novo <= first[p.cabeca]:
                first[p.cabeca] |= novo
                mudou = True
    return first


def first_sequencia(seq, first: dict[str, set[str]], g: Gramatica) -> set[str]:
    """FIRST(X1 X2 ... Xn) para uma sequência de símbolos."""
    resultado: set[str] = set()
    for s in seq:
        if not g.eh_nao_terminal(s):
            resultado.add(s)
            return resultado
        resultado |= first[s] - {EPSILON}
        if EPSILON not in first[s]:
            return resultado
    resultado.add(EPSILON)  # todos os símbolos derivam ε (ou a sequência é vazia)
    return resultado


def calcular_follow(g: Gramatica, first: dict[str, set[str]]) -> dict[str, set[str]]:
    """FOLLOW de cada não terminal."""
    follow: dict[str, set[str]] = {nt: set() for nt in g.nao_terminais}
    follow[g.inicial].add(FIM)  # regra 1: $ ∈ FOLLOW(S)
    mudou = True
    while mudou:
        mudou = False
        for p in g.producoes:
            for i, b in enumerate(p.corpo):
                if not g.eh_nao_terminal(b):
                    continue
                beta = first_sequencia(p.corpo[i + 1:], first, g)
                novo = beta - {EPSILON}  # regra 2: A → αBβ ⇒ FIRST(β)−{ε} ⊆ FOLLOW(B)
                if EPSILON in beta:  # regra 3: β ⇒* ε ⇒ FOLLOW(A) ⊆ FOLLOW(B)
                    novo |= follow[p.cabeca]
                if not novo <= follow[b]:
                    follow[b] |= novo
                    mudou = True
    return follow

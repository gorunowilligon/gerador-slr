"""Itens LR(0), CLOSURE (fig. 4.32), GOTO e coleção canônica (fig. 4.33)."""

from __future__ import annotations

from .gramatica import Gramatica

Item = tuple[int, int]  # (índice da produção, posição do ponto)


def simbolo_apos_ponto(g: Gramatica, item: Item) -> str | None:
    prod, ponto = item
    corpo = g.producoes[prod].corpo
    return corpo[ponto] if ponto < len(corpo) else None


def closure(g: Gramatica, itens) -> tuple[Item, ...]:
    """Fig. 4.32: adiciona B → ·γ para todo item A → α·Bβ, até não haver mudança.

    Devolve uma tupla ordenada (ordem de descoberta) para que a numeração dos
    estados seja determinística e igual à do livro.
    """
    resultado: list[Item] = list(dict.fromkeys(itens))
    presentes = set(resultado)
    i = 0
    while i < len(resultado):
        b = simbolo_apos_ponto(g, resultado[i])
        if b is not None and g.eh_nao_terminal(b):
            for prod in g.por_cabeca[b]:
                novo = (prod, 0)
                if novo not in presentes:
                    presentes.add(novo)
                    resultado.append(novo)
        i += 1
    return tuple(resultado)


def goto(g: Gramatica, itens, simbolo: str) -> tuple[Item, ...]:
    """GOTO(I, X) = CLOSURE({A → αX·β | A → α·Xβ ∈ I})."""
    nucleo = [(p, d + 1) for (p, d) in itens if simbolo_apos_ponto(g, (p, d)) == simbolo]
    return closure(g, nucleo) if nucleo else ()


class ColecaoCanonica:
    """Fig. 4.33: coleção canônica de conjuntos de itens LR(0)."""

    def __init__(self, g: Gramatica):
        self.g = g
        self.estados: list[tuple[Item, ...]] = [closure(g, [(0, 0)])]
        self.transicoes: dict[tuple[int, str], int] = {}
        indice = {frozenset(self.estados[0]): 0}
        i = 0
        while i < len(self.estados):
            estado = self.estados[i]
            simbolos = list(dict.fromkeys(
                s for s in (simbolo_apos_ponto(g, it) for it in estado) if s is not None
            ))
            for x in simbolos:
                destino = goto(g, estado, x)
                chave = frozenset(destino)
                if chave not in indice:
                    indice[chave] = len(self.estados)
                    self.estados.append(destino)
                self.transicoes[(i, x)] = indice[chave]
            i += 1

    def formatar_item(self, item: Item) -> str:
        prod, ponto = item
        p = self.g.producoes[prod]
        corpo = list(p.corpo)
        corpo.insert(ponto, "·")
        return f"{p.cabeca} ::= {' '.join(corpo)}"

    def __str__(self) -> str:
        linhas = []
        for i, estado in enumerate(self.estados):
            linhas.append(f"I{i}:")
            linhas.extend("    " + self.formatar_item(it) for it in estado)
            saidas = [f"{x} → I{j}" for (k, x), j in self.transicoes.items() if k == i]
            if saidas:
                linhas.append("    GOTO: " + ", ".join(saidas))
        return "\n".join(linhas)

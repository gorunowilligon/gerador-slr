"""Algoritmo 4.46 (Aho 2ª ed.) — construção da tabela de análise SLR."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .first_follow import calcular_first, calcular_follow
from .gramatica import FIM, Gramatica
from .lr0 import ColecaoCanonica

# Ação: ("s", j) empilha e vai para j | ("r", p) reduz pela produção p | ("acc",) aceita


def acao_str(acao) -> str:
    if acao[0] == "acc":
        return "acc"
    return f"{acao[0]}{acao[1]}"


def acao_de_str(texto: str):
    if texto == "acc":
        return ("acc",)
    return (texto[0], int(texto[1:]))


@dataclass
class Conflito:
    estado: int
    terminal: str
    existente: tuple
    nova: tuple
    escolhida: tuple | None = None

    @property
    def tipo(self) -> str:
        tipos = {self.existente[0], self.nova[0]}
        return "shift/reduce" if tipos == {"s", "r"} else "reduce/reduce"

    def __str__(self) -> str:
        texto = (f"estado {self.estado}, terminal {self.terminal!r}: {self.tipo} "
                 f"({acao_str(self.existente)} × {acao_str(self.nova)})")
        if self.escolhida:
            texto += f" → resolvido como {acao_str(self.escolhida)}"
        return texto


@dataclass
class TabelaSLR:
    gramatica: Gramatica
    acao: list[dict[str, tuple]]
    desvio: list[dict[str, int]]
    conflitos: list[Conflito] = field(default_factory=list)
    first: dict[str, set[str]] = field(default_factory=dict)
    follow: dict[str, set[str]] = field(default_factory=dict)
    colecao: ColecaoCanonica | None = None
    reservadas: list[str] = field(default_factory=list)

    @property
    def terminais(self) -> list[str]:
        return self.gramatica.terminais + [FIM]

    # ---------------------------------------------------------------- JSON
    def para_dict(self) -> dict:
        g = self.gramatica
        return {
            "simbolo_inicial": g.inicial_original,
            "producoes": [[p.cabeca, list(p.corpo)] for p in g.producoes[1:]],
            "terminais": self.terminais,
            "nao_terminais": g.nao_terminais,
            "reservadas": self.reservadas,
            "acao": [{t: acao_str(a) for t, a in linha.items()} for linha in self.acao],
            "desvio": self.desvio,
        }

    def salvar(self, caminho: str) -> None:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(self.para_dict(), f, ensure_ascii=False, indent=1)

    @classmethod
    def carregar(cls, caminho: str) -> "TabelaSLR":
        from .gramatica import Producao

        with open(caminho, encoding="utf-8-sig") as f:
            d = json.load(f)
        g = Gramatica([Producao(c, tuple(corpo)) for c, corpo in d["producoes"]])
        return cls(
            gramatica=g,
            acao=[{t: acao_de_str(a) for t, a in linha.items()} for linha in d["acao"]],
            desvio=[{nt: int(j) for nt, j in linha.items()} for linha in d["desvio"]],
            reservadas=d.get("reservadas", []),
        )

    # ------------------------------------------------------------ exibição
    def formatar(self) -> str:
        """Tabela ACTION | GOTO em texto, no estilo da fig. 4.37 do livro."""
        terms = self.terminais
        nts = [nt for nt in self.gramatica.nao_terminais if nt != self.gramatica.inicial]
        cab = ["estado"] + terms + ["|"] + nts
        linhas = []
        for i in range(len(self.acao)):
            linha = [str(i)]
            linha += [acao_str(self.acao[i][t]) if t in self.acao[i] else "" for t in terms]
            linha += ["|"]
            linha += [str(self.desvio[i][nt]) if nt in self.desvio[i] else "" for nt in nts]
            linhas.append(linha)
        larguras = [max(len(c), *(len(l[k]) for l in linhas)) for k, c in enumerate(cab)]
        fmt = lambda l: " ".join(c.center(w) for c, w in zip(l, larguras))
        sep = "-" * len(fmt(cab))
        return "\n".join([fmt(cab), sep] + [fmt(l) for l in linhas])


def construir_tabela(g: Gramatica, resolver_conflitos: bool = False) -> TabelaSLR:
    """Algoritmo SLR.

    1. Constrói a coleção canônica C = {I0..In} de itens LR(0).
    2. Para o estado i:
       a) [A → α·aβ] ∈ Ii e GOTO(Ii, a) = Ij  ⇒  ACTION[i, a] = shift j
       b) [A → α·]   ∈ Ii, A ≠ S'             ⇒  ACTION[i, a] = reduce A → α, ∀a ∈ FOLLOW(A)
       c) [S' → S·]  ∈ Ii                     ⇒  ACTION[i, $] = accept
    3. GOTO(Ii, A) = Ij  ⇒  GOTO[i, A] = j
    Se houver entradas múltiplas a gramática não é SLR(1). Com
    resolver_conflitos=True usa a política do yacc: shift vence reduce, e
    entre dois reduces vence a produção definida primeiro.
    """
    first = calcular_first(g)
    follow = calcular_follow(g, first)
    colecao = ColecaoCanonica(g)
    n = len(colecao.estados)
    acao: list[dict[str, tuple]] = [{} for _ in range(n)]
    desvio: list[dict[str, int]] = [{} for _ in range(n)]
    conflitos: list[Conflito] = []

    def definir(i: int, a: str, nova: tuple) -> None:
        atual = acao[i].get(a)
        if atual is None or atual == nova:
            acao[i][a] = nova
            return
        c = Conflito(i, a, atual, nova)
        if resolver_conflitos:
            if atual[0] == "s":
                escolhida = atual
            elif nova[0] == "s":
                escolhida = nova
            else:
                escolhida = min(atual, nova, key=lambda x: x[1])
            acao[i][a] = c.escolhida = escolhida
        conflitos.append(c)

    for i, estado in enumerate(colecao.estados):
        for prod, ponto in estado:
            p = g.producoes[prod]
            if ponto < len(p.corpo):
                a = p.corpo[ponto]
                if not g.eh_nao_terminal(a):
                    definir(i, a, ("s", colecao.transicoes[(i, a)]))
            elif prod == 0:
                definir(i, FIM, ("acc",))
            else:
                for a in sorted(follow[p.cabeca], key=_ordem_terminais(g)):
                    definir(i, a, ("r", prod))
        for (k, x), j in colecao.transicoes.items():
            if k == i and g.eh_nao_terminal(x):
                desvio[i][x] = j

    return TabelaSLR(g, acao, desvio, conflitos, first, follow, colecao)


def _ordem_terminais(g: Gramatica):
    ordem = {t: k for k, t in enumerate(g.terminais + [FIM])}
    return lambda t: ordem.get(t, len(ordem))

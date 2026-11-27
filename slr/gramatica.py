"""Leitura e representação de Gramáticas Livres de Contexto.

Formato de entrada (uma produção por linha):

    ⟨Não terminal⟩ ::= ⟨Corpo da produção⟩

* não terminais aparecem entre ⟨ e ⟩   (aceita-se também <X> em ASCII);
* terminais "especiais" são escritos literalmente entre “ e ”  (ou "...");
* terminais nomeados (id, num, palavras reservadas...) são palavras soltas;
* & representa a palavra vazia (ε);
* extensões opcionais: alternativas com | na mesma linha, linhas iniciadas
  por | continuam a produção anterior, e linhas iniciadas por # são comentários.

A cabeça da primeira produção é o símbolo inicial.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

EPSILON = "&"
FIM = "$"


class ErroGramatica(Exception):
    """Erro na definição da gramática."""


@dataclass(frozen=True)
class Producao:
    cabeca: str
    corpo: tuple[str, ...]  # tupla vazia = produção vazia (&)

    def __str__(self) -> str:
        return f"{self.cabeca} ::= {' '.join(self.corpo) if self.corpo else EPSILON}"


_CABECA = re.compile(r"^\s*(⟨[^⟩]+⟩|<[^<>\s]+>)\s*::=(.*)$")
_SIMBOLO = re.compile(
    r"""
      ⟨(?P<nt>[^⟩]+)⟩            # não terminal unicode
    | <(?P<nt2>[^<>\s]+)>        # não terminal ascii
    | “(?P<lit>[^”]+)”           # terminal literal unicode
    | "(?P<lit2>[^"]+)"          # terminal literal ascii
    | (?P<solto>\S+)             # terminal nomeado, & ou |
    """,
    re.VERBOSE,
)


def nome_nt(nome: str) -> str:
    return f"⟨{nome.strip()}⟩"


def _ler_corpo(texto: str, num_linha: int) -> list[tuple[str, ...]]:
    """Divide o corpo em alternativas; cada alternativa é uma tupla de símbolos."""
    alternativas: list[list[str]] = [[]]
    pos = 0
    texto = texto.strip()
    while pos < len(texto):
        if texto[pos].isspace():
            pos += 1
            continue
        m = _SIMBOLO.match(texto, pos)
        if not m:  # pragma: no cover - o padrão \S+ sempre casa
            raise ErroGramatica(f"linha {num_linha}: símbolo inválido em {texto[pos:]!r}")
        pos = m.end()
        if m.group("nt") or m.group("nt2"):
            alternativas[-1].append(nome_nt(m.group("nt") or m.group("nt2")))
        elif m.group("lit") or m.group("lit2"):
            alternativas[-1].append(m.group("lit") or m.group("lit2"))
        else:
            simbolo = m.group("solto")
            if simbolo == "|":
                alternativas.append([])
            elif simbolo == EPSILON:
                pass  # & não ocupa posição no corpo
            else:
                alternativas[-1].append(simbolo)
    return [tuple(a) for a in alternativas]


class Gramatica:
    """Gramática aumentada: a produção 0 é sempre S' ::= S."""

    def __init__(self, producoes: list[Producao]):
        if not producoes:
            raise ErroGramatica("a gramática não possui produções")
        self.inicial_original = producoes[0].cabeca
        self.inicial = self.inicial_original[:-1] + "'⟩"
        while any(p.cabeca == self.inicial for p in producoes):
            self.inicial = self.inicial[:-1] + "'⟩"
        self.producoes: list[Producao] = [Producao(self.inicial, (self.inicial_original,))] + producoes

        self.nao_terminais: list[str] = []
        for p in self.producoes:
            if p.cabeca not in self.nao_terminais:
                self.nao_terminais.append(p.cabeca)
        conjunto_nt = set(self.nao_terminais)

        self.terminais: list[str] = []
        indefinidos: list[str] = []
        for p in self.producoes:
            for s in p.corpo:
                if s.startswith("⟨") and s.endswith("⟩") and len(s) > 2:
                    if s not in conjunto_nt and s not in indefinidos:
                        indefinidos.append(s)
                elif s not in self.terminais:
                    self.terminais.append(s)
        if indefinidos:
            raise ErroGramatica("não terminais usados mas nunca definidos: " + ", ".join(indefinidos))
        if FIM in self.terminais:
            raise ErroGramatica(f"o símbolo {FIM} é reservado para o fim da entrada")

        self.por_cabeca: dict[str, list[int]] = {nt: [] for nt in self.nao_terminais}
        for i, p in enumerate(self.producoes):
            self.por_cabeca[p.cabeca].append(i)

        self.avisos: list[str] = []
        alcancaveis = self._alcancaveis()
        for nt in self.nao_terminais:
            if nt not in alcancaveis:
                self.avisos.append(f"não terminal inalcançável: {nt}")

    def eh_nao_terminal(self, simbolo: str) -> bool:
        return simbolo in self.por_cabeca

    def _alcancaveis(self) -> set[str]:
        vistos = {self.inicial}
        pilha = [self.inicial]
        while pilha:
            nt = pilha.pop()
            for i in self.por_cabeca[nt]:
                for s in self.producoes[i].corpo:
                    if self.eh_nao_terminal(s) and s not in vistos:
                        vistos.add(s)
                        pilha.append(s)
        return vistos

    @classmethod
    def ler(cls, texto: str) -> "Gramatica":
        producoes: list[Producao] = []
        cabeca_atual: str | None = None
        for num, linha in enumerate(texto.splitlines(), start=1):
            limpa = linha.strip()
            if not limpa or limpa.startswith("#"):
                continue
            m = _CABECA.match(linha)
            if m:
                cabeca_atual = nome_nt(m.group(1)[1:-1])
                corpo = m.group(2)
            elif limpa.startswith("|") and cabeca_atual:
                corpo = limpa[1:]
            else:
                raise ErroGramatica(
                    f"linha {num}: esperado '⟨Não terminal⟩ ::= corpo', encontrado {limpa!r}"
                )
            for alt in _ler_corpo(corpo, num):
                producoes.append(Producao(cabeca_atual, alt))
        return cls(producoes)

    @classmethod
    def ler_arquivo(cls, caminho: str) -> "Gramatica":
        with open(caminho, encoding="utf-8-sig") as f:
            return cls.ler(f.read())

    def __str__(self) -> str:
        largura = len(str(len(self.producoes) - 1))
        return "\n".join(f"{i:>{largura}}: {p}" for i, p in enumerate(self.producoes))

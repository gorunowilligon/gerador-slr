"""Tabela de símbolos (TS).

Regras do enunciado:
* as palavras reservadas são armazenadas a priori, com categoria PR;
* se o lexema já está na TS, retorna-se o token lá indicado
  (ex.: ⟨for, PR⟩ ou ⟨id, 10⟩ se o id já foi visto antes);
* senão o lexema é incluído e o token é ⟨classe, linha_da_TS⟩, ex.: ⟨id, 10⟩.
"""

from __future__ import annotations

from dataclasses import dataclass

from .tokens import Token

PR = "PR"


@dataclass
class Entrada:
    lexema: str
    classe: str  # "PR" para palavras reservadas; senão id, num, texto...


class TabelaSimbolos:
    def __init__(self, reservadas: list[str] | None = None):
        self.entradas: list[Entrada] = []
        self._indice: dict[str, int] = {}
        for r in reservadas or []:
            self.inserir(r, PR)

    def inserir(self, lexema: str, classe: str) -> int:
        if lexema in self._indice:
            return self._indice[lexema]
        self.entradas.append(Entrada(lexema, classe))
        self._indice[lexema] = len(self.entradas)  # linhas numeradas a partir de 1
        return self._indice[lexema]

    def token_para(self, lexema: str, classe: str) -> Token:
        """Consulta a TS; insere se necessário; devolve o token adequado."""
        if lexema in self._indice:
            linha = self._indice[lexema]
            entrada = self.entradas[linha - 1]
            if entrada.classe == PR:
                return Token(lexema, PR)
            return Token(entrada.classe, linha)
        return Token(classe, self.inserir(lexema, classe))

    def __len__(self) -> int:
        return len(self.entradas)

    def __str__(self) -> str:
        larg = max([6] + [len(e.lexema) for e in self.entradas])
        linhas = [f"{'linha':>5}  {'lexema':<{larg}}  categoria", "-" * (larg + 20)]
        for i, e in enumerate(self.entradas, start=1):
            cat = "Palavra-Reservada" if e.classe == PR else e.classe
            linhas.append(f"{i:>5}  {e.lexema:<{larg}}  {cat}")
        return "\n".join(linhas)

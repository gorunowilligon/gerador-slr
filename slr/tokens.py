"""Tokens e o formato textual da lista de tokens (saída do léxico / entrada do sintático).

Um token por linha:

    ⟨id, 3⟩          identificador na linha 3 da tabela de símbolos
    ⟨se, PR⟩         palavra reservada
    ⟨num, 7⟩         constante na linha 7 da tabela de símbolos
    ⟨(⟩              símbolo especial (o token é só o símbolo)

Opcionalmente a linha termina com  <TAB># linha:coluna  (posição no fonte),
usada apenas para mensagens de erro. Aceita-se também < e > em ASCII.
Linhas vazias ou iniciadas por # são ignoradas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Token:
    tipo: str                 # nome do terminal na gramática
    atributo: str | int = ""  # índice na TS, "PR" ou vazio
    linha: int | None = None
    coluna: int | None = None

    def __str__(self) -> str:
        return f"⟨{self.tipo}, {self.atributo}⟩" if self.atributo != "" else f"⟨{self.tipo}⟩"

    def posicao(self) -> str:
        return f"linha {self.linha}, coluna {self.coluna}" if self.linha is not None else ""

    def para_linha(self) -> str:
        sufixo = f"\t# {self.linha}:{self.coluna}" if self.linha is not None else ""
        return str(self) + sufixo


class ErroTokens(Exception):
    pass


def ler_token(texto: str, num_linha: int = 0) -> Token:
    linha = col = None
    if "\t#" in texto:
        texto, pos = texto.split("\t#", 1)
        try:
            linha, col = (int(x) for x in pos.strip().split(":"))
        except ValueError:
            pass
    texto = texto.strip()
    if len(texto) >= 3 and (texto[0], texto[-1]) in (("⟨", "⟩"), ("<", ">")):
        interno = texto[1:-1]
    else:
        raise ErroTokens(f"linha {num_linha}: token mal formado {texto!r} (esperado ⟨tipo, atributo⟩)")
    corte = interno.find(", ", 1)  # o tipo nunca é vazio; ⟨,⟩ é o token vírgula
    if corte == -1:
        tipo, atributo = interno, ""
    else:
        tipo, atributo = interno[:corte], interno[corte + 2:].strip()
    if atributo.isdigit():
        atributo = int(atributo)
    return Token(tipo.strip() or tipo, atributo, linha, col)


_VARIOS = re.compile(r"⟨.+?⟩(?=\s|$)")


def ler_tokens(texto: str) -> list[Token]:
    """Aceita três formas, misturáveis linha a linha:
    * um token por linha: ⟨id, 3⟩   (ou <id, 3>)
    * vários tokens numa linha: ⟨id, 1⟩ ⟨+⟩ ⟨id, 2⟩
    * forma simplificada, só os terminais separados por espaço: id + id * id
    Um $ final é opcional (o fim da entrada é acrescentado automaticamente).
    """
    tokens = []
    for n, linha in enumerate(texto.splitlines(), start=1):
        limpa = linha.strip()
        if not limpa or limpa.startswith("#"):
            continue
        if limpa.startswith("⟨") and "\t#" not in linha and len(_VARIOS.findall(limpa)) > 1:
            tokens.extend(ler_token(t, n) for t in _VARIOS.findall(limpa))
        elif limpa.startswith("⟨") or (limpa.startswith("<") and limpa.endswith(">") and len(limpa) >= 3):
            tokens.append(ler_token(linha, n))
        else:
            tokens.extend(Token(t) for t in limpa.split())
    if tokens and tokens[-1].tipo == "$" and tokens[-1].atributo == "":
        tokens.pop()
    return tokens


def ler_arquivo_tokens(caminho: str) -> list[Token]:
    with open(caminho, encoding="utf-8-sig") as f:
        return ler_tokens(f.read())


def escrever_tokens(tokens: list[Token]) -> str:
    return "\n".join(t.para_linha() for t in tokens) + "\n"

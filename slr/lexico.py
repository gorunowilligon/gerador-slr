"""Analisador léxico dirigido por uma definição regular (substituto do Trabalho I).

Formato da definição léxica (uma regra por linha):

    nome: expressão_regular              token ⟨nome, lexema⟩
    nome @ts: expressão_regular          consulta/insere na TS → ⟨nome, linha⟩ ou ⟨lexema, PR⟩
    nome @ignorar: expressão_regular     reconhecido e descartado (espaços, comentários)
    @literais: ( ) { } ; == =  ...       símbolos especiais: o token é o próprio símbolo

As expressões usam a sintaxe de expressões regulares do Python. A escolha entre
regras segue o casamento mais longo; em empate vence a regra definida primeiro.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .tabela_simbolos import TabelaSimbolos
from .tokens import Token


class ErroLexico(Exception):
    pass


@dataclass
class Regra:
    nome: str
    padrao: re.Pattern
    modo: str  # "normal" | "ts" | "ignorar" | "literal"


_REGRA = re.compile(r"^\s*(?P<nome>@literais|[A-Za-z_]\w*)\s*(?P<modo>@\w+)?\s*:(?P<er>.*)$")


def ler_definicao(texto: str) -> list[Regra]:
    regras: list[Regra] = []
    for n, linha in enumerate(texto.splitlines(), start=1):
        if not linha.strip() or linha.lstrip().startswith("#"):
            continue
        m = _REGRA.match(linha)
        if not m:
            raise ErroLexico(f"definição léxica, linha {n}: esperado 'nome: expressão'")
        nome, modo, er = m.group("nome"), (m.group("modo") or "@normal")[1:], m.group("er").strip()
        if nome == "@literais":
            for simbolo in er.split():
                regras.append(Regra(simbolo, re.compile(re.escape(simbolo)), "literal"))
            continue
        if modo not in ("normal", "ts", "ignorar"):
            raise ErroLexico(f"definição léxica, linha {n}: modo desconhecido @{modo}")
        try:
            padrao = re.compile(er)
        except re.error as e:
            raise ErroLexico(f"definição léxica, linha {n}: expressão inválida ({e})") from None
        if padrao.match(""):
            raise ErroLexico(f"definição léxica, linha {n}: a expressão de '{nome}' aceita a cadeia vazia")
        regras.append(Regra(nome, padrao, modo))
    return regras


def ler_arquivo_definicao(caminho: str) -> list[Regra]:
    with open(caminho, encoding="utf-8-sig") as f:
        return ler_definicao(f.read())


def analisar_lexico(regras: list[Regra], fonte: str, ts: TabelaSimbolos):
    """Devolve (tokens, erros). Em caso de caractere inválido, registra o erro e avança."""
    tokens: list[Token] = []
    erros: list[str] = []
    pos, linha, inicio_linha = 0, 1, 0
    while pos < len(fonte):
        melhor: tuple[int, Regra] | None = None
        for r in regras:
            m = r.padrao.match(fonte, pos)
            if m and m.end() > pos and (melhor is None or m.end() > melhor[0]):
                melhor = (m.end(), r)
        coluna = pos - inicio_linha + 1
        if melhor is None:
            erros.append(f"erro léxico na linha {linha}, coluna {coluna}: caractere inesperado {fonte[pos]!r}")
            fim = pos + 1
        else:
            fim, regra = melhor
            lexema = fonte[pos:fim]
            tok = None
            if regra.modo == "ts":
                tok = ts.token_para(lexema, regra.nome)
            elif regra.modo == "literal":
                tok = Token(lexema)
            elif regra.modo == "normal":
                tok = Token(regra.nome, lexema)
            if tok is not None:
                tok.linha, tok.coluna = linha, coluna
                tokens.append(tok)
        trecho = fonte[pos:fim]
        if "\n" in trecho:
            linha += trecho.count("\n")
            inicio_linha = pos + trecho.rfind("\n") + 1
        pos = fim
    return tokens, erros

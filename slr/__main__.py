"""Interface de linha de comando.

    python -m slr projeto  GRAMATICA RESERVADAS [-o DIR] [--resolver-conflitos]
    python -m slr lexico   DEF_LEXICA FONTE -t DIR/tabela.json [-o tokens.txt]
    python -m slr executar DIR/tabela.json TOKENS [-o pilha.txt]
    python -m slr rodar    DIR_LINGUAGEM FONTE        (projeto + léxico + execução)
"""

from __future__ import annotations

import argparse
import os
import sys

from .analisador import analisar
from .gramatica import EPSILON, ErroGramatica, Gramatica
from .lexico import ErroLexico, analisar_lexico, ler_arquivo_definicao
from .tabela_simbolos import TabelaSimbolos
from .tabela_slr import TabelaSLR, construir_tabela
from .tokens import ErroTokens, escrever_tokens, ler_arquivo_tokens


def _titulo(texto: str) -> str:
    return f"\n=== {texto} " + "=" * max(0, 70 - len(texto))


def ler_reservadas(caminho: str) -> list[str]:
    with open(caminho, encoding="utf-8-sig") as f:
        return [p for linha in f if not linha.lstrip().startswith("#") for p in linha.split()]


def relatorio(tab: TabelaSLR) -> str:
    g = tab.gramatica
    fmt = lambda c: "{ " + ", ".join(sorted(c, key=lambda t: (t in (EPSILON, "$"), t))) + " }"
    partes = [_titulo("Gramática aumentada"), str(g)]
    if g.avisos:
        partes += ["", *("AVISO: " + a for a in g.avisos)]
    partes.append(_titulo("FIRST e FOLLOW"))
    larg = max(len(nt) for nt in g.nao_terminais)
    for nt in g.nao_terminais:
        partes.append(f"{nt:<{larg}}  FIRST = {fmt(tab.first[nt])}")
        partes.append(f"{'':<{larg}}  FOLLOW = {fmt(tab.follow[nt])}")
    partes += [_titulo(f"Coleção canônica LR(0) — {len(tab.colecao.estados)} estados"), str(tab.colecao)]
    partes += [_titulo("Tabela SLR (ACTION | GOTO)"), tab.formatar()]
    if tab.conflitos:
        partes += [_titulo(f"{len(tab.conflitos)} conflito(s) — a gramática NÃO é SLR(1)"),
                   *map(str, tab.conflitos)]
    else:
        partes += ["", "Sem conflitos: a gramática é SLR(1)."]
    return "\n".join(partes) + "\n"


def gerar_projeto(caminho_gram: str, caminho_res: str, saida: str, resolver: bool, verbose=True):
    g = Gramatica.ler_arquivo(caminho_gram)
    reservadas = ler_reservadas(caminho_res) if caminho_res else []
    tab = construir_tabela(g, resolver)
    tab.reservadas = reservadas
    for r in reservadas:
        if r not in g.terminais:
            g.avisos.append(f"palavra reservada {r!r} não aparece como terminal na gramática")
    os.makedirs(saida, exist_ok=True)
    texto = relatorio(tab)
    with open(os.path.join(saida, "relatorio.txt"), "w", encoding="utf-8") as f:
        f.write(texto)
    ts = TabelaSimbolos(reservadas)
    with open(os.path.join(saida, "ts_inicial.txt"), "w", encoding="utf-8") as f:
        f.write(str(ts) + "\n")
    if verbose:
        print(texto)
        print(_titulo("Tabela de símbolos inicial (palavras reservadas)"))
        print(ts)
    if tab.conflitos and not resolver:
        print("\nA tabela NÃO foi salva por causa dos conflitos acima. Corrija a gramática "
              "ou use --resolver-conflitos (shift vence reduce, como no yacc).", file=sys.stderr)
        return None
    tab.salvar(os.path.join(saida, "tabela.json"))
    if verbose:
        print(f"\nArquivos gerados em {saida}: tabela.json, relatorio.txt, ts_inicial.txt")
    return tab


def gerar_tokens(caminho_def: str, caminho_fonte: str, tab: TabelaSLR):
    regras = ler_arquivo_definicao(caminho_def)
    with open(caminho_fonte, encoding="utf-8-sig") as f:
        fonte = f.read()
    ts = TabelaSimbolos(tab.reservadas)
    tokens, erros = analisar_lexico(regras, fonte, ts)
    desconhecidos = sorted({t.tipo for t in tokens} - set(tab.gramatica.terminais))
    if desconhecidos:
        erros.append("tokens que não são terminais da gramática: " + ", ".join(desconhecidos))
    return tokens, ts, erros


def executar(tab: TabelaSLR, tokens, saida: str | None, largura: int) -> bool:
    res = analisar(tab, tokens, largura)
    texto = res.formatar()
    print(_titulo("Pilha de execução"))
    print(texto)
    if saida:
        with open(saida, "w", encoding="utf-8") as f:
            f.write(texto + "\n")
    return res.aceito


def main(argv=None) -> int:
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")
        except AttributeError:  # pragma: no cover
            pass

    ap = argparse.ArgumentParser(prog="python -m slr", description="Gerador de analisadores SLR")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("projeto", help="interface de projeto: gramática + reservadas → tabela SLR")
    p.add_argument("gramatica")
    p.add_argument("reservadas", nargs="?", help="arquivo com as palavras reservadas (opcional)")
    p.add_argument("-o", "--saida", default="build")
    p.add_argument("--resolver-conflitos", action="store_true")

    p = sub.add_parser("lexico", help="gera a lista de tokens de um fonte")
    p.add_argument("definicao")
    p.add_argument("fonte")
    p.add_argument("-t", "--tabela", default="build/tabela.json")
    p.add_argument("-o", "--saida", default="tokens.txt")

    p = sub.add_parser("executar", help="interface de execução: tokens → pilha de execução")
    p.add_argument("tabela")
    p.add_argument("tokens")
    p.add_argument("-o", "--saida")
    p.add_argument("--largura", type=int, default=6, help="tokens de entrada exibidos por passo (0 = todos)")

    p = sub.add_parser("rodar", help="projeto + léxico + execução para uma pasta de linguagem")
    p.add_argument("linguagem", help="pasta com gramatica.txt, reservadas.txt e lexico.txt")
    p.add_argument("fonte")
    p.add_argument("--largura", type=int, default=6)
    p.add_argument("--resolver-conflitos", action="store_true")

    sub.add_parser("gui", help="abre a interface gráfica")

    a = ap.parse_args(argv)
    if a.cmd == "gui":
        from .gui import main as gui_main
        gui_main()
        return 0
    try:
        if a.cmd == "projeto":
            return 0 if gerar_projeto(a.gramatica, a.reservadas, a.saida, a.resolver_conflitos) else 2

        if a.cmd == "lexico":
            tab = TabelaSLR.carregar(a.tabela)
            tokens, ts, erros = gerar_tokens(a.definicao, a.fonte, tab)
            with open(a.saida, "w", encoding="utf-8") as f:
                f.write(escrever_tokens(tokens))
            with open(os.path.splitext(a.saida)[0] + "_ts.txt", "w", encoding="utf-8") as f:
                f.write(str(ts) + "\n")
            print(_titulo("Tokens"))
            print(escrever_tokens(tokens), end="")
            print(_titulo("Tabela de símbolos"))
            print(ts)
            for e in erros:
                print(e, file=sys.stderr)
            return 1 if erros else 0

        if a.cmd == "executar":
            tab = TabelaSLR.carregar(a.tabela)
            return 0 if executar(tab, ler_arquivo_tokens(a.tokens), a.saida, a.largura) else 1

        if a.cmd == "rodar":
            d = a.linguagem
            saida = os.path.join(d, "build")
            tab = gerar_projeto(os.path.join(d, "gramatica.txt"), os.path.join(d, "reservadas.txt"),
                                saida, a.resolver_conflitos, verbose=False)
            if tab is None:
                return 2
            print(f"Tabela SLR gerada: {len(tab.acao)} estados "
                  f"(detalhes em {os.path.join(saida, 'relatorio.txt')})")
            tokens, ts, erros = gerar_tokens(os.path.join(d, "lexico.txt"), a.fonte, tab)
            base = os.path.join(saida, os.path.splitext(os.path.basename(a.fonte))[0])
            with open(base + "_tokens.txt", "w", encoding="utf-8") as f:
                f.write(escrever_tokens(tokens))
            print(_titulo("Tokens"))
            print(" ".join(map(str, tokens)))
            print(_titulo("Tabela de símbolos"))
            print(ts)
            if erros:
                print("\n" + "\n".join(erros), file=sys.stderr)
                print("RESULTADO: código REJEITADO na análise léxica.")
                return 1
            return 0 if executar(tab, tokens, base + "_pilha.txt", a.largura) else 1
    except (ErroGramatica, ErroLexico, ErroTokens, OSError) as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

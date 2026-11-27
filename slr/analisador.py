"""Algoritmo 4.44 (fig. 4.36) — análise LR dirigida pela tabela, com registro da pilha."""

from __future__ import annotations

from dataclasses import dataclass, field

from .gramatica import FIM
from .tabela_slr import TabelaSLR, acao_str
from .tokens import Token


@dataclass
class Passo:
    pilha: str
    entrada: str
    acao: str


@dataclass
class Resultado:
    aceito: bool
    passos: list[Passo] = field(default_factory=list)
    erro: str | None = None

    def formatar(self) -> str:
        cab = ("passo", "pilha", "entrada", "ação")
        linhas = [(str(i + 1), p.pilha, p.entrada, p.acao) for i, p in enumerate(self.passos)]
        larg = [max(len(cab[k]), *(len(l[k]) for l in linhas)) if linhas else len(cab[k])
                for k in range(4)]
        fmt = lambda l: f"{l[0]:>{larg[0]}}  {l[1]:<{larg[1]}}  {l[2]:>{larg[2]}}  {l[3]}"
        saida = [fmt(cab), "-" * (sum(larg) + 6 + 4)] + [fmt(l) for l in linhas]
        saida.append("")
        if self.aceito:
            saida.append("RESULTADO: código ACEITO — sintaticamente correto.")
        else:
            saida.append("RESULTADO: código REJEITADO — " + (self.erro or "erro sintático"))
        return "\n".join(saida)


def analisar(tabela: TabelaSLR, tokens: list[Token], max_entrada: int = 6) -> Resultado:
    """Executa o analisador LR sobre a lista de tokens.

    pilha guarda estados (como no livro); simbolos é mantida em paralelo só para exibição.
    """
    g = tabela.gramatica
    entrada = list(tokens) + [Token(FIM, "")]
    pilha = [0]
    simbolos: list[str] = []
    passos: list[Passo] = []
    ip = 0

    def foto_pilha() -> str:
        partes = [str(pilha[0])]
        for s, e in zip(simbolos, pilha[1:]):
            partes += [s, str(e)]
        return " ".join(partes)

    def foto_entrada() -> str:
        resto = [t.tipo for t in entrada[ip:]]
        if len(resto) > max_entrada > 0:
            resto = resto[:max_entrada] + ["…"]
        return " ".join(resto)

    while True:
        s = pilha[-1]
        a = entrada[ip]
        acao = tabela.acao[s].get(a.tipo)
        if acao is None:
            esperados = sorted(tabela.acao[s], key=lambda t: (t == FIM, t))
            onde = f" ({a.posicao()})" if a.posicao() else f" (token nº {ip + 1})"
            achado = "fim da entrada" if a.tipo == FIM else str(a)
            erro = (f"erro sintático em {achado}{onde}; esperado: "
                    + ", ".join(esperados))
            passos.append(Passo(foto_pilha(), foto_entrada(), "ERRO"))
            return Resultado(False, passos, erro)

        if acao[0] == "s":
            passos.append(Passo(foto_pilha(), foto_entrada(), f"empilha {acao[1]}"))
            pilha.append(acao[1])
            simbolos.append(a.tipo)
            ip += 1
        elif acao[0] == "r":
            p = g.producoes[acao[1]]
            passos.append(Passo(foto_pilha(), foto_entrada(), f"reduz {acao_str(acao)}: {p}"))
            n = len(p.corpo)
            if n:
                del pilha[-n:]
                del simbolos[-n:]
            topo = pilha[-1]
            if p.cabeca not in tabela.desvio[topo]:  # só ocorre com tabela corrompida
                return Resultado(False, passos, f"GOTO[{topo}, {p.cabeca}] indefinido")
            pilha.append(tabela.desvio[topo][p.cabeca])
            simbolos.append(p.cabeca)
        else:
            passos.append(Passo(foto_pilha(), foto_entrada(), "aceita"))
            return Resultado(True, passos)

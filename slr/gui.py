"""Interface gráfica (tkinter, já vem com o Python):   python -m slr gui"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from .analisador import analisar
from .gramatica import EPSILON, FIM, ErroGramatica, Gramatica
from .lexico import ErroLexico, analisar_lexico, ler_definicao
from .tabela_simbolos import PR, TabelaSimbolos
from .tabela_slr import acao_str, construir_tabela
from .tokens import ErroTokens, ler_tokens

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQS_DEFINICAO = {"gramatica.txt", "reservadas.txt", "lexico.txt"}
VERDE, VERMELHO, AMARELO = "#d4edda", "#f8d7da", "#fff3cd"


def ler(caminho: str) -> str:
    with open(caminho, encoding="utf-8-sig") as f:
        return f.read()


def listar_exemplos() -> dict[str, str]:
    exemplos = {}
    for base in ("linguagens", "exemplos"):
        pasta = os.path.join(RAIZ, base)
        if os.path.isdir(pasta):
            for nome in sorted(os.listdir(pasta)):
                p = os.path.join(pasta, nome)
                if os.path.isfile(os.path.join(p, "gramatica.txt")):
                    exemplos[f"{base}/{nome}"] = p
    return exemplos


def palavras(texto: str) -> list[str]:
    return [p for linha in texto.splitlines() if not linha.lstrip().startswith("#") for p in linha.split()]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gerador de analisadores SLR")
        self.geometry("1360x800")
        self.minsize(900, 560)
        familias = set(tkfont.families())
        mono = next((f for f in ("Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Menlo") if f in familias),
                    "TkFixedFont")
        self.fonte = tkfont.Font(family=mono, size=11)
        self.fonte_tab = tkfont.Font(family=mono, size=10)
        estilo = ttk.Style(self)
        estilo.configure("Treeview", font=self.fonte_tab, rowheight=self.fonte_tab.metrics("linespace") + 6)
        estilo.configure("Treeview.Heading", font=(mono, 10))  # negrito não tem os glifos ⟨ ⟩
        estilo.configure("Resultado.TLabel", font=(mono, 12), padding=8)

        self.exemplos = listar_exemplos()
        self.pasta: str | None = None
        self.tabela = None
        self.executavel = False
        self.assinatura_gerada = None

        self._barra()
        self._corpo()
        self.status = ttk.Label(self, relief="sunken", anchor="w", padding=(8, 2))
        self.status.pack(fill="x", side="bottom")
        self.bind("<F5>", lambda e: self.gerar())
        self.bind("<F6>", lambda e: self.executar())
        if self.exemplos:
            primeiro = next(iter(self.exemplos))
            self.cb_exemplo.set(primeiro)
            self.carregar_pasta(self.exemplos[primeiro])

    # ------------------------------------------------------------- layout
    def _barra(self):
        b = ttk.Frame(self, padding=6)
        b.pack(fill="x")
        ttk.Label(b, text="Exemplo:").pack(side="left")
        self.cb_exemplo = ttk.Combobox(b, values=list(self.exemplos), state="readonly", width=30)
        self.cb_exemplo.pack(side="left", padx=4)
        self.cb_exemplo.bind("<<ComboboxSelected>>",
                             lambda e: self.carregar_pasta(self.exemplos[self.cb_exemplo.get()]))
        ttk.Button(b, text="Abrir pasta…", command=self.abrir_pasta).pack(side="left", padx=2)
        ttk.Button(b, text="Salvar gramática…", command=self.salvar_gramatica).pack(side="left", padx=2)
        ttk.Separator(b, orient="vertical").pack(side="left", fill="y", padx=8)
        self.var_resolver = tk.BooleanVar(value=False)
        ttk.Checkbutton(b, text="Resolver conflitos (shift vence)", variable=self.var_resolver).pack(side="left")
        ttk.Button(b, text="▶ Analisar entrada (F6)", command=self.executar).pack(side="right", padx=2)
        ttk.Button(b, text="⚙ Gerar tabela (F5)", command=self.gerar).pack(side="right", padx=2)

    def _texto(self, pai, altura):
        f = ttk.Frame(pai)
        t = tk.Text(f, height=altura, wrap="none", undo=True, font=self.fonte)
        ys = ttk.Scrollbar(f, orient="vertical", command=t.yview)
        xs = ttk.Scrollbar(f, orient="horizontal", command=t.xview)
        t.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        t.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)
        return f, t

    def _arvore(self, pai):
        f = ttk.Frame(pai)
        tv = ttk.Treeview(f, show="headings")
        ys = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        xs = ttk.Scrollbar(f, orient="horizontal", command=tv.xview)
        tv.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        tv.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)
        tv.tag_configure("erro", background=VERMELHO)
        tv.tag_configure("ok", background=VERDE)
        tv.tag_configure("conflito", background=AMARELO)
        return f, tv

    def _corpo(self):
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=6)

        # tamanhos pedidos fixos: senão a tabela larga "rouba" todo o espaço do editor
        caixa_esq = ttk.Frame(pw, width=420, height=600)
        caixa_esq.pack_propagate(False)
        caixa_dir = ttk.Frame(pw, width=910, height=600)
        caixa_dir.pack_propagate(False)
        pw.add(caixa_esq, weight=2)
        pw.add(caixa_dir, weight=5)

        # ---- esquerda: interface de projeto
        esq = ttk.PanedWindow(caixa_esq, orient="vertical")
        esq.pack(fill="both", expand=True)
        lf = ttk.LabelFrame(esq, text=" Gramática   ⟨A⟩ ::= corpo   |  “x” literal  |  & vazio ", padding=4)
        f, self.txt_gram = self._texto(lf, 18)
        f.pack(fill="both", expand=True)
        esq.add(lf, weight=5)
        lf = ttk.LabelFrame(esq, text=" Palavras reservadas ", padding=4)
        f, self.txt_res = self._texto(lf, 3)
        f.pack(fill="both", expand=True)
        esq.add(lf, weight=1)
        lf = ttk.LabelFrame(esq, text=" Definição léxica (só para entrada em código-fonte) ", padding=4)
        f, self.txt_lex = self._texto(lf, 6)
        f.pack(fill="both", expand=True)
        esq.add(lf, weight=2)

        # ---- direita: abas
        self.nb = ttk.Notebook(caixa_dir)
        self.nb.pack(fill="both", expand=True)

        aba = ttk.Frame(self.nb, padding=4)
        f, self.tv_tabela = self._arvore(aba)
        f.pack(fill="both", expand=True)
        self.nb.add(aba, text="Tabela SLR")

        aba = ttk.Frame(self.nb, padding=4)
        f, self.tv_ff = self._arvore(aba)
        f.pack(fill="both", expand=True)
        self.nb.add(aba, text="FIRST / FOLLOW")

        aba = ttk.Frame(self.nb, padding=4)
        f, self.txt_itens = self._texto(aba, 10)
        f.pack(fill="both", expand=True)
        self.nb.add(aba, text="Itens LR(0)")

        self.aba_exec = ttk.Frame(self.nb, padding=4)
        self._aba_execucao(self.aba_exec)
        self.nb.add(self.aba_exec, text="Execução")

        aba = ttk.PanedWindow(self.nb, orient="horizontal")
        lf = ttk.LabelFrame(aba, text=" Tokens ", padding=4)
        f, self.txt_tokens = self._texto(lf, 10)
        f.pack(fill="both", expand=True)
        aba.add(lf, weight=1)
        lf = ttk.LabelFrame(aba, text=" Tabela de símbolos ", padding=4)
        f, self.tv_ts = self._arvore(lf)
        f.pack(fill="both", expand=True)
        aba.add(lf, weight=1)
        self.nb.add(aba, text="Tokens / TS")

        self.aba_msg = ttk.Frame(self.nb, padding=4)
        f, self.txt_msg = self._texto(self.aba_msg, 10)
        f.pack(fill="both", expand=True)
        self.nb.add(self.aba_msg, text="Mensagens")

    def _aba_execucao(self, aba):
        topo = ttk.Frame(aba)
        topo.pack(fill="x")
        ttk.Label(topo, text="Entrada:").pack(side="left")
        self.cb_entrada = ttk.Combobox(topo, state="readonly", width=28)
        self.cb_entrada.pack(side="left", padx=4)
        self.cb_entrada.bind("<<ComboboxSelected>>", lambda e: self.carregar_entrada(self.cb_entrada.get()))
        ttk.Button(topo, text="Abrir arquivo…", command=self.abrir_entrada).pack(side="left", padx=2)
        self.var_modo = tk.StringVar(value="tokens")
        ttk.Radiobutton(topo, text="Lista de tokens", value="tokens", variable=self.var_modo).pack(side="left", padx=(12, 2))
        ttk.Radiobutton(topo, text="Código-fonte (usa o léxico)", value="fonte", variable=self.var_modo).pack(side="left")

        pw = ttk.PanedWindow(aba, orient="vertical")
        pw.pack(fill="both", expand=True, pady=(4, 0))
        lf = ttk.LabelFrame(pw, text=" ⟨id, 1⟩ um por linha, ou só os terminais separados por espaço: id + id * id ",
                            padding=4)
        f, self.txt_entrada = self._texto(lf, 7)
        f.pack(fill="both", expand=True)
        pw.add(lf, weight=1)

        baixo = ttk.Frame(pw)
        self.lbl_resultado = ttk.Label(baixo, text="", style="Resultado.TLabel", anchor="w")
        self.lbl_resultado.pack(fill="x")
        f, self.tv_passos = self._arvore(baixo)
        self.pilhas_completas: list[str] = []
        self.tv_passos.bind("<<TreeviewSelect>>", self._mostrar_pilha)
        f.pack(fill="both", expand=True)
        pw.add(baixo, weight=3)

    # ------------------------------------------------------------ helpers
    def _preencher(self, tv, colunas, linhas, tags=None, alinhar_esq=(), maximos=None, alinhar_dir=()):
        tv.delete(*tv.get_children())
        tv["columns"] = [f"c{i}" for i in range(len(colunas))]
        for i, nome in enumerate(colunas):
            textos = [nome] + [str(l[i]) for l in linhas[:400]]
            largura = max(self.fonte_tab.measure(t) for t in textos) + 18
            tv.heading(f"c{i}", text=nome)
            limite = (maximos or {}).get(i, 900)
            ancora = "w" if i in alinhar_esq else "e" if i in alinhar_dir else "center"
            tv.column(f"c{i}", width=min(largura, limite), minwidth=30, stretch=False, anchor=ancora)
        for k, l in enumerate(linhas):
            tv.insert("", "end", values=[str(x) for x in l], tags=(tags[k],) if tags and tags[k] else ())

    def _set_texto(self, t, conteudo):
        t.delete("1.0", "end")
        t.insert("1.0", conteudo)

    def _msg(self, texto, cor=None):
        self.status.configure(text=texto, background=cor or "")

    def _assinatura(self):
        return (self.txt_gram.get("1.0", "end"), self.txt_res.get("1.0", "end"), self.var_resolver.get())

    def _mostrar_ts(self, ts: TabelaSimbolos):
        linhas = [(i, e.lexema, "Palavra-Reservada" if e.classe == PR else e.classe)
                  for i, e in enumerate(ts.entradas, start=1)]
        self._preencher(self.tv_ts, ["linha", "lexema", "categoria"], linhas, alinhar_esq=(1, 2))

    # ----------------------------------------------------------- arquivos
    def carregar_pasta(self, pasta: str):
        self.pasta = pasta
        arq = lambda n: os.path.join(pasta, n)
        self._set_texto(self.txt_gram, ler(arq("gramatica.txt")))
        self._set_texto(self.txt_res, ler(arq("reservadas.txt")) if os.path.exists(arq("reservadas.txt")) else "")
        self._set_texto(self.txt_lex, ler(arq("lexico.txt")) if os.path.exists(arq("lexico.txt")) else "")
        entradas = sorted(n for n in os.listdir(pasta)
                          if os.path.isfile(arq(n)) and n not in ARQS_DEFINICAO)
        self.cb_entrada["values"] = entradas
        self._set_texto(self.txt_entrada, "")
        if entradas:
            self.cb_entrada.set(entradas[0])
            self.carregar_entrada(entradas[0])
        else:
            self.cb_entrada.set("")
        self.lbl_resultado.configure(text="", background="")
        self.tv_passos.delete(*self.tv_passos.get_children())
        self.var_resolver.set("nao_slr" in pasta or "pendente" in pasta)
        self.gerar()

    def carregar_entrada(self, nome: str, caminho: str | None = None):
        caminho = caminho or os.path.join(self.pasta or "", nome)
        self._set_texto(self.txt_entrada, ler(caminho))
        self.var_modo.set("tokens" if caminho.endswith(".txt") else "fonte")

    def abrir_pasta(self):
        pasta = filedialog.askdirectory(title="Pasta com gramatica.txt (e opcionalmente reservadas.txt, lexico.txt)",
                                        initialdir=RAIZ)
        if not pasta:
            return
        if not os.path.isfile(os.path.join(pasta, "gramatica.txt")):
            messagebox.showerror("Pasta inválida", "A pasta precisa conter um arquivo gramatica.txt.")
            return
        self.cb_exemplo.set(os.path.basename(pasta))
        self.carregar_pasta(pasta)

    def abrir_entrada(self):
        caminho = filedialog.askopenfilename(title="Arquivo de entrada (tokens ou código-fonte)",
                                             initialdir=self.pasta or RAIZ)
        if caminho:
            self.cb_entrada.set(os.path.basename(caminho))
            self.carregar_entrada("", caminho)
            self.nb.select(self.aba_exec)

    def salvar_gramatica(self):
        caminho = filedialog.asksaveasfilename(title="Salvar gramática", defaultextension=".txt",
                                               initialdir=self.pasta or RAIZ, initialfile="gramatica.txt")
        if caminho:
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(self.txt_gram.get("1.0", "end-1c"))
            self._msg(f"Gramática salva em {caminho}")

    # -------------------------------------------------- interface de projeto
    def gerar(self) -> bool:
        self.assinatura_gerada = self._assinatura()
        self.tabela, self.executavel = None, False
        try:
            g = Gramatica.ler(self.txt_gram.get("1.0", "end"))
        except ErroGramatica as e:
            self._set_texto(self.txt_msg, f"Erro na gramática:\n{e}")
            self.nb.select(self.aba_msg)
            self._msg(f"✘ Erro na gramática: {e}", VERMELHO)
            return False
        reservadas = palavras(self.txt_res.get("1.0", "end"))
        resolver = self.var_resolver.get()
        tab = construir_tabela(g, resolver)
        tab.reservadas = reservadas

        # tabela ACTION | GOTO
        conflitos: dict[tuple[int, str], list[str]] = {}
        for c in tab.conflitos:
            conflitos.setdefault((c.estado, c.terminal), [acao_str(c.existente)]).append(acao_str(c.nova))
        nts = [nt for nt in g.nao_terminais if nt != g.inicial]
        linhas, tags = [], []
        for i in range(len(tab.acao)):
            linha = [i]
            for t in tab.terminais:
                if (i, t) in conflitos:
                    opcoes = "/".join(dict.fromkeys(conflitos[(i, t)]))
                    linha.append(f"{acao_str(tab.acao[i][t])}!" if resolver else opcoes)
                else:
                    linha.append(acao_str(tab.acao[i][t]) if t in tab.acao[i] else "")
            linha += [tab.desvio[i].get(nt, "") for nt in nts]
            linhas.append(linha)
            tags.append("conflito" if any(k[0] == i for k in conflitos) else "")
        cab = ["estado"] + [f"{t}" for t in tab.terminais] + nts
        self._preencher(self.tv_tabela, cab, linhas, tags)

        # FIRST / FOLLOW
        fmt = lambda c: "{ " + ", ".join(sorted(c, key=lambda t: (t in (EPSILON, FIM), t))) + " }"
        self._preencher(self.tv_ff, ["não terminal", "FIRST", "FOLLOW"],
                        [(nt, fmt(tab.first[nt]), fmt(tab.follow[nt])) for nt in g.nao_terminais],
                        alinhar_esq=(0, 1, 2))
        self._set_texto(self.txt_itens, str(tab.colecao))
        self._mostrar_ts(TabelaSimbolos(reservadas))
        self._set_texto(self.txt_tokens, "")

        msgs = ["Gramática aumentada (número = índice usado em rN):", str(g), ""]
        msgs += [f"AVISO: {a}" for a in g.avisos]
        msgs += [f"AVISO: palavra reservada {r!r} não aparece na gramática" for r in reservadas if r not in g.terminais]
        if tab.conflitos:
            msgs += ["", f"{len(tab.conflitos)} conflito(s) — a gramática NÃO é SLR(1):"]
            msgs += [f"  {c}" for c in tab.conflitos]
        self._set_texto(self.txt_msg, "\n".join(msgs))

        resumo = f"{len(tab.acao)} estados · {len(g.terminais)} terminais · {len(nts)} não terminais · {len(g.producoes) - 1} produções"
        if not tab.conflitos:
            self._msg(f"✔ Gramática SLR(1) — {resumo}", VERDE)
        elif resolver:
            self._msg(f"⚠ {len(tab.conflitos)} conflito(s) resolvidos por shift (células com '!') — {resumo}", AMARELO)
        else:
            self._msg(f"✘ {len(tab.conflitos)} conflito(s): a gramática NÃO é SLR(1) — veja as linhas amarelas "
                      f"e a aba Mensagens — {resumo}", VERMELHO)
        self.tabela = tab
        self.executavel = not tab.conflitos or resolver
        self.nb.select(0)
        return True

    # ------------------------------------------------- interface de execução
    def executar(self):
        if self._assinatura() != self.assinatura_gerada and not self.gerar():
            return
        if not self.executavel:
            messagebox.showwarning("Tabela com conflitos",
                                   "A gramática não é SLR(1). Corrija-a ou marque "
                                   "'Resolver conflitos' para analisar mesmo assim.")
            return
        tab = self.tabela
        entrada = self.txt_entrada.get("1.0", "end")
        self.nb.select(self.aba_exec)
        try:
            if self.var_modo.get() == "tokens":
                tokens = ler_tokens(entrada)
            else:
                definicao = self.txt_lex.get("1.0", "end")
                if not definicao.strip():
                    raise ErroLexico("para analisar código-fonte preencha a definição léxica (à esquerda)")
                ts = TabelaSimbolos(tab.reservadas)
                tokens, erros = analisar_lexico(ler_definicao(definicao), entrada, ts)
                self._mostrar_ts(ts)
                self._set_texto(self.txt_tokens, "\n".join(t.para_linha() for t in tokens))
                if erros:
                    self._resultado(False, "erro léxico — " + "; ".join(erros))
                    self.tv_passos.delete(*self.tv_passos.get_children())
                    return
        except (ErroTokens, ErroLexico) as e:
            self._resultado(False, str(e))
            return

        desconhecidos = sorted({t.tipo for t in tokens} - set(tab.gramatica.terminais))
        res = analisar(tab, tokens, max_entrada=8)
        self.pilhas_completas = [p.pilha for p in res.passos]
        linhas = [(i + 1, self._encurtar(p.pilha, 44), p.entrada, p.acao) for i, p in enumerate(res.passos)]
        tags = [""] * len(linhas)
        if tags:
            tags[-1] = "ok" if res.aceito else "erro"
        # pilhas longas são cortadas à esquerda: o topo (a parte que importa) continua visível;
        # clicar numa linha mostra a pilha inteira na barra de status
        self._preencher(self.tv_passos, ["passo", "pilha (topo à direita)", "entrada", "ação"], linhas, tags,
                        alinhar_esq=(1, 3), alinhar_dir=(2,), maximos={2: 250})
        if linhas:
            self.tv_passos.see(self.tv_passos.get_children()[-1])
        extra = f"   (tokens que não são terminais da gramática: {', '.join(desconhecidos)})" if desconhecidos else ""
        self._resultado(res.aceito, (res.erro or "") + extra, len(tokens), len(res.passos))

    @staticmethod
    def _encurtar(pilha: str, maximo: int) -> str:
        if len(pilha) <= maximo:
            return pilha
        corte = pilha.find(" ", len(pilha) - maximo)
        return "… " + pilha[corte + 1:]

    def _mostrar_pilha(self, _evento=None):
        sel = self.tv_passos.selection()
        if sel:
            i = self.tv_passos.index(sel[0])
            if i < len(self.pilhas_completas):
                self._msg(f"passo {i + 1} — pilha: {self.pilhas_completas[i]}")

    def _resultado(self, aceito: bool, detalhe: str = "", ntok: int = 0, npassos: int = 0):
        if aceito:
            texto, cor = f"✔ ACEITO — sintaticamente correto  ({ntok} tokens, {npassos} passos)", VERDE
        else:
            texto, cor = f"✘ REJEITADO — {detalhe}", VERMELHO
        self.lbl_resultado.configure(text=texto, background=cor, wraplength=self.aba_exec.winfo_width() - 20)
        self._msg(texto, cor)


def main():
    try:  # nitidez em telas com escala no Windows
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App().mainloop()


if __name__ == "__main__":
    main()

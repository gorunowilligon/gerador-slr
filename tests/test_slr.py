import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from slr.analisador import analisar
from slr.first_follow import calcular_first, calcular_follow
from slr.gramatica import ErroGramatica, Gramatica
from slr.lexico import analisar_lexico, ler_definicao
from slr.tabela_simbolos import TabelaSimbolos
from slr.tabela_slr import TabelaSLR, acao_str, construir_tabela
from slr.tokens import Token, escrever_tokens, ler_tokens

# Gramática 4.1 do livro (expressões), no formato do enunciado
G41 = """
⟨E⟩ ::= ⟨E⟩ “+” ⟨T⟩
⟨E⟩ ::= ⟨T⟩
⟨T⟩ ::= ⟨T⟩ “*” ⟨F⟩
⟨T⟩ ::= ⟨F⟩
⟨F⟩ ::= “(” ⟨E⟩ “)”
⟨F⟩ ::= id
"""

# Gramática 4.28 (sem recursão à esquerda) — para FIRST/FOLLOW
G428 = """
<E>  ::= <T> <E2>
<E2> ::= "+" <T> <E2> | &
<T>  ::= <F> <T2>
<T2> ::= "*" <F> <T2> | &
<F>  ::= "(" <E> ")" | id
"""


def toks(*tipos):
    return [Token(t, 1 if t == "id" else "") for t in tipos]


class TestGramatica(unittest.TestCase):
    def test_leitura(self):
        g = Gramatica.ler(G41)
        self.assertEqual(len(g.producoes), 7)  # + produção aumentada
        self.assertEqual(g.inicial, "⟨E'⟩")
        self.assertEqual(g.terminais, ["+", "*", "(", ")", "id"])
        self.assertEqual(g.producoes[5].corpo, ("(", "⟨E⟩", ")"))

    def test_epsilon_e_alternativas(self):
        g = Gramatica.ler(G428)
        vazias = [str(p) for p in g.producoes if not p.corpo]
        self.assertEqual(vazias, ["⟨E2⟩ ::= &", "⟨T2⟩ ::= &"])

    def test_nao_terminal_indefinido(self):
        with self.assertRaises(ErroGramatica):
            Gramatica.ler("⟨S⟩ ::= a ⟨X⟩")

    def test_linha_invalida(self):
        with self.assertRaises(ErroGramatica):
            Gramatica.ler("S -> a")


class TestFirstFollow(unittest.TestCase):
    def test_exemplo_4_30(self):
        g = Gramatica.ler(G428)
        first = calcular_first(g)
        follow = calcular_follow(g, first)
        self.assertEqual(first["⟨E⟩"], {"(", "id"})
        self.assertEqual(first["⟨E2⟩"], {"+", "&"})
        self.assertEqual(first["⟨T2⟩"], {"*", "&"})
        self.assertEqual(follow["⟨E⟩"], {")", "$"})
        self.assertEqual(follow["⟨E2⟩"], {")", "$"})
        self.assertEqual(follow["⟨T⟩"], {"+", ")", "$"})
        self.assertEqual(follow["⟨T2⟩"], {"+", ")", "$"})
        self.assertEqual(follow["⟨F⟩"], {"+", "*", ")", "$"})


class TestTabela(unittest.TestCase):
    def setUp(self):
        self.tab = construir_tabela(Gramatica.ler(G41))

    def test_doze_estados_sem_conflito(self):
        self.assertEqual(len(self.tab.colecao.estados), 12)
        self.assertEqual(self.tab.conflitos, [])

    def test_figura_4_37(self):
        # ACTION da fig. 4.37 (numeração de estados e produções idêntica à do livro)
        esperado = {
            0: {"id": "s5", "(": "s4"},
            1: {"+": "s6", "$": "acc"},
            2: {"+": "r2", "*": "s7", ")": "r2", "$": "r2"},
            3: {"+": "r4", "*": "r4", ")": "r4", "$": "r4"},
            4: {"id": "s5", "(": "s4"},
            5: {"+": "r6", "*": "r6", ")": "r6", "$": "r6"},
            6: {"id": "s5", "(": "s4"},
            7: {"id": "s5", "(": "s4"},
            8: {"+": "s6", ")": "s11"},
            9: {"+": "r1", "*": "s7", ")": "r1", "$": "r1"},
            10: {"+": "r3", "*": "r3", ")": "r3", "$": "r3"},
            11: {"+": "r5", "*": "r5", ")": "r5", "$": "r5"},
        }
        obtido = {i: {t: acao_str(a) for t, a in l.items()} for i, l in enumerate(self.tab.acao)}
        self.assertEqual(obtido, esperado)
        self.assertEqual(self.tab.desvio[0], {"⟨E⟩": 1, "⟨T⟩": 2, "⟨F⟩": 3})
        self.assertEqual(self.tab.desvio[4], {"⟨E⟩": 8, "⟨T⟩": 2, "⟨F⟩": 3})
        self.assertEqual(self.tab.desvio[6], {"⟨T⟩": 9, "⟨F⟩": 3})
        self.assertEqual(self.tab.desvio[7], {"⟨F⟩": 10})

    def test_figura_4_38(self):
        r = analisar(self.tab, toks("id", "*", "id", "+", "id"))
        self.assertTrue(r.aceito)
        self.assertEqual(len(r.passos), 14)  # mesmos 14 movimentos do livro
        self.assertEqual(r.passos[0].pilha, "0")
        self.assertEqual(r.passos[5].pilha, "0 ⟨T⟩ 2 * 7 id 5")  # movimento (6) do livro
        self.assertEqual(r.passos[-1].acao, "aceita")

    def test_rejeita(self):
        r = analisar(self.tab, toks("id", "+", "*", "id"))
        self.assertFalse(r.aceito)
        self.assertIn("esperado: (, id", r.erro)
        r = analisar(self.tab, toks("(", "id"))
        self.assertFalse(r.aceito)
        self.assertIn("fim da entrada", r.erro)

    def test_json_ida_e_volta(self):
        with tempfile.TemporaryDirectory() as d:
            caminho = os.path.join(d, "t.json")
            self.tab.salvar(caminho)
            t2 = TabelaSLR.carregar(caminho)
        self.assertEqual(t2.acao, self.tab.acao)
        self.assertEqual(t2.desvio, self.tab.desvio)
        self.assertTrue(analisar(t2, toks("(", "id", ")", "*", "id")).aceito)

    def test_gramatica_4_49_nao_slr(self):
        g = Gramatica.ler("""
            ⟨S⟩ ::= ⟨L⟩ “=” ⟨R⟩ | ⟨R⟩
            ⟨L⟩ ::= “*” ⟨R⟩ | id
            ⟨R⟩ ::= ⟨L⟩
        """)
        tab = construir_tabela(g)
        self.assertEqual(len(tab.conflitos), 1)
        c = tab.conflitos[0]
        self.assertEqual((c.estado, c.terminal, c.tipo), (2, "=", "shift/reduce"))

    def test_resolucao_shift(self):
        g = Gramatica.ler("""
            ⟨S⟩ ::= if ⟨S⟩ | if ⟨S⟩ else ⟨S⟩ | a
        """)
        tab = construir_tabela(g, resolver_conflitos=True)
        self.assertTrue(tab.conflitos)
        self.assertTrue(analisar(tab, toks("if", "if", "a", "else", "a")).aceito)


class TestLexicoETS(unittest.TestCase):
    DEF = r"""
    ws @ignorar: \s+
    id @ts: [A-Za-z_]\w*
    num @ts: \d+
    @literais: ( ) = == ,
    """

    def test_tabela_de_simbolos(self):
        ts = TabelaSimbolos(["for", "if"])
        tokens, erros = analisar_lexico(ler_definicao(self.DEF), "for x == 10 , x ( y )", ts)
        self.assertEqual(erros, [])
        self.assertEqual([str(t) for t in tokens],
                         ["⟨for, PR⟩", "⟨id, 3⟩", "⟨==⟩", "⟨num, 4⟩", "⟨,⟩",
                          "⟨id, 3⟩", "⟨(⟩", "⟨id, 5⟩", "⟨)⟩"])
        self.assertEqual(len(ts), 5)

    def test_posicao_e_erro(self):
        tokens, erros = analisar_lexico(ler_definicao(self.DEF), "x\n  y $", TabelaSimbolos())
        self.assertEqual((tokens[1].linha, tokens[1].coluna), (2, 3))
        self.assertEqual(len(erros), 1)
        self.assertIn("linha 2, coluna 5", erros[0])

    def test_formato_tokens_ida_e_volta(self):
        tokens, _ = analisar_lexico(ler_definicao(self.DEF), "if (a, 1) == b", TabelaSimbolos(["if"]))
        relidos = ler_tokens(escrever_tokens(tokens))
        self.assertEqual([(t.tipo, t.atributo, t.linha) for t in relidos],
                         [(t.tipo, t.atributo, t.linha) for t in tokens])
        self.assertEqual(ler_tokens("<id, 10>\n⟨,⟩")[1].tipo, ",")


if __name__ == "__main__":
    unittest.main()

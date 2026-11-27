# Gerador de Analisadores Sintáticos SLR

Arcabouço em Python puro (≥ 3.10, sem dependências) que gera analisadores SLR
a partir de uma Gramática Livre de Contexto, seguindo o livro do Aho (seção 4.6).

| Algoritmo do enunciado | Arquivo |
|---|---|
| (a) FIRST e FOLLOW (4.4.2) | [slr/first_follow.py](slr/first_follow.py) |
| (b) CLOSURE (fig. 4.32) | [slr/lr0.py](slr/lr0.py) — `closure` |
| (c) Coleção canônica (fig. 4.33) | [slr/lr0.py](slr/lr0.py) — `ColecaoCanonica` |
| (d) Análise LR (alg. 4.44, fig. 4.36) | [slr/analisador.py](slr/analisador.py) |
| (e) Tabela SLR | [slr/tabela_slr.py](slr/tabela_slr.py) |
| Tabela de símbolos | [slr/tabela_simbolos.py](slr/tabela_simbolos.py) |
| Analisador léxico | [slr/lexico.py](slr/lexico.py) |

## Interface gráfica

```bash
python -m slr gui
```
À esquerda fica a interface de projeto: gramática, palavras reservadas e
definição léxica, editáveis. **F5** gera a tabela. As abas mostram a tabela
ACTION|GOTO (linhas com conflito em amarelo), FIRST/FOLLOW e os itens LR(0).
Na aba **Execução**, **F6** analisa a entrada, que pode ser uma lista de tokens
ou código-fonte, e mostra a pilha passo a passo com o resultado em verde ou
vermelho. Clique num passo para ver a pilha inteira na barra de status. O menu
"Exemplo" carrega qualquer pasta de `exemplos/` ou `linguagens/`.

## Gramáticas de teste ([exemplos/](exemplos/))

Cada pasta tem `gramatica.txt`, às vezes `reservadas.txt`, e entradas `aceita*.txt` / `rejeita*.txt`.

| Pasta | O que testa |
|---|---|
| 01_expressoes | gramática 4.1 do livro; tabela = fig. 4.37, `aceita_fig_4_38` = fig. 4.38 |
| 02_expressoes_ll1 | gramática 4.28, muitas produções & (FIRST/FOLLOW do ex. 4.30) |
| 03_parenteses | parênteses balanceados, aceita a entrada vazia |
| 04_anbn | aⁿbⁿ (livre de contexto, não regular) |
| 05_declaracoes_c | declarações C, tokens no formato do léxico (`⟨int, PR⟩ ⟨id, 4⟩`) |
| 06_mini_pascal | comandos, blocos, while, if-then-else, comando vazio |
| 07_json | objetos e listas JSON |
| 08_nao_slr_4_49 | gramática 4.49: **não é SLR** (conflito shift/reduce no estado 2) |
| 09_else_pendente | ambígua; resolvida por shift, o else fica com o if mais próximo |

## Linha de comando

```bash
# tudo de uma vez: projeto + léxico + execução
python -m slr rodar linguagens/receita linguagens/receita/correto.rct
python -m slr rodar linguagens/receita linguagens/receita/erro.rct
```

### Interface de projeto
```bash
python -m slr projeto GRAMATICA.txt RESERVADAS.txt -o build
```
Mostra a gramática aumentada, FIRST/FOLLOW, a coleção canônica LR(0), a tabela
ACTION|GOTO e a tabela de símbolos inicial (palavras reservadas). Gera
`build/tabela.json`, `build/relatorio.txt` e `build/ts_inicial.txt`.
Se houver conflitos, eles são listados e a tabela não é salva — a menos que se
use `--resolver-conflitos` (shift vence reduce, como no yacc).

### Interface de execução
```bash
python -m slr lexico   LEXICO.txt FONTE -t build/tabela.json -o tokens.txt   # fonte → tokens
python -m slr executar build/tabela.json tokens.txt [-o pilha.txt] [--largura 0]
```
A saída é a pilha de execução, passo a passo (pilha | entrada | ação), e o
resultado: **ACEITO** ou **REJEITADO** (com linha/coluna e terminais esperados).
Código de saída: 0 aceito, 1 rejeitado, 2 erro na definição.

## Formatos

**Gramática** — uma produção por linha:
```
⟨E⟩ ::= ⟨E⟩ “+” ⟨T⟩
⟨F⟩ ::= id
⟨L⟩ ::= &
```
Não terminais entre `⟨ ⟩`, símbolos especiais entre `“ ”`, terminais nomeados
(`id`, `num`, palavras reservadas) soltos, `&` = ε. A primeira cabeça é o símbolo
inicial. Também se aceitam `<X>` e `"x"` em ASCII, `|` para alternativas e `#` para comentários.

**Palavras reservadas** — separadas por espaço ou quebra de linha.

**Lista de tokens** — um por linha: `⟨id, 16⟩`, `⟨se, PR⟩`, `⟨num, 20⟩`, `⟨(⟩`.
Vários tokens podem ir na mesma linha. Para testes rápidos basta escrever só os
terminais separados por espaço, como em `id + id * id`.
Um sufixo opcional `<TAB># linha:coluna` serve só para mensagens de erro.

**Tabela de símbolos** — as palavras reservadas são inseridas a priori
(categoria PR). Ao ler um lexema de uma classe marcada `@ts`: se ele já está na
TS, devolve-se o token de lá (`⟨se, PR⟩` ou `⟨id, 16⟩`); senão ele é inserido
e devolve-se `⟨id, linha⟩`. O mesmo vale para constantes (`num`, `texto`).

**Definição léxica** (ver [linguagens/receita/lexico.txt](linguagens/receita/lexico.txt)):
```
espaco @ignorar: [ \t\r\n]+
id     @ts:      [A-Za-z_][A-Za-z0-9_]*
@literais: ( ) { } ; == =
```
Casamento mais longo; em empate vence a regra escrita primeiro.

## A linguagem RECEITA

Programas são receitas: `receita` declara funções, `ingrediente` declara
variáveis, `prove` lê, `anote` escreve, `sirva` retorna, `se/senao`,
`enquanto` e `repita N vezes { ... }`. A gramática é SLR(1): 107 estados, sem conflitos.

```
receita fatorial(n) {
    ingrediente resultado = 1;
    enquanto (n > 1) { resultado = resultado * n; n = n - 1; }
    sirva resultado;
}
```

Arquivos em [linguagens/receita/](linguagens/receita/): `gramatica.txt`,
`reservadas.txt`, `lexico.txt`, `correto.rct` e `erro.rct` (falta um `;`).

## Testes

```bash
python -m unittest discover -s tests -v
```
Conferem o FIRST/FOLLOW do exemplo 4.30, a tabela exata da fig. 4.37, os 14
movimentos da fig. 4.38, o conflito da gramática 4.49 (não SLR) e a TS.

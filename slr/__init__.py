"""Arcabouço para geração de analisadores sintáticos SLR (Aho et al., seção 4.6)."""

from .analisador import analisar
from .gramatica import Gramatica
from .tabela_slr import TabelaSLR, construir_tabela

__all__ = ["Gramatica", "TabelaSLR", "construir_tabela", "analisar"]

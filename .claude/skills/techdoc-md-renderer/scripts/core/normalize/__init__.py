"""Adapters between the legacy dict AST and the Phase 2 DocumentModel."""

from .ast_to_model import ast_to_document
from .model_to_ast import document_to_ast

__all__ = ["ast_to_document", "document_to_ast"]

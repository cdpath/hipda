from __future__ import annotations

import logging
import warnings

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=SyntaxWarning, module=r"jieba(\..*)?")
    import jieba


_jieba_initialized = False


def _ensure_jieba_initialized() -> None:
    global _jieba_initialized
    if not _jieba_initialized:
        jieba.setLogLevel(logging.WARNING)
        jieba.initialize()
        _jieba_initialized = True


def segment_text(text: str) -> str:
    """Segment ``text`` into whitespace-joined tokens so the default FTS5
    ``unicode61`` tokenizer can find token boundaries inside CJK content.

    ASCII text remains effectively unchanged (jieba keeps Latin words whole),
    Chinese phrases get broken into jieba's dictionary segments.
    """
    if not text:
        return ""
    _ensure_jieba_initialized()
    tokens = [token for token in jieba.cut(text) if token and not token.isspace()]
    return " ".join(tokens)

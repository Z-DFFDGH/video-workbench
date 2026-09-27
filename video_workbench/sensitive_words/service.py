from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SENSITIVE_WORDS_FILE_NAME = "sensitive_words.txt"


class SensitiveWordsError(Exception):
    """Base exception for local sensitive word errors."""


class SensitiveWordsFileNotFoundError(SensitiveWordsError):
    """Raised when the local sensitive word file does not exist."""


class SensitiveWordsValidationError(SensitiveWordsError):
    """Raised when the sensitive word file cannot be read."""


def default_sensitive_words_path() -> Path:
    """Return the editable word file stored beside the program source."""
    return Path(__file__).resolve().parents[2] / SENSITIVE_WORDS_FILE_NAME


@dataclass(frozen=True, slots=True)
class SensitiveWordsLibrary:
    path: Path
    words: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SensitiveMatch:
    word: str
    matched_text: str
    start: int
    end: int
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class SensitiveCheckResult:
    word_count: int
    matches: tuple[SensitiveMatch, ...]

    @property
    def match_count(self) -> int:
        return len(self.matches)


def _normalized_word_key(word: str) -> str:
    return word.lower()


def _load_words(path: Path) -> tuple[str, ...]:
    try:
        content = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as error:
        raise SensitiveWordsFileNotFoundError(
            f"敏感词词库不存在：{path}"
        ) from error
    except (OSError, UnicodeError) as error:
        raise SensitiveWordsValidationError(
            f"无法读取敏感词词库：{path}"
        ) from error

    words: list[str] = []
    seen: set[str] = set()
    for raw_line in content.splitlines():
        word = raw_line.strip()
        if not word:
            continue
        key = _normalized_word_key(word)
        if key in seen:
            continue
        seen.add(key)
        words.append(word)
    return tuple(words)


def _line_and_column(text: str, start: int) -> tuple[int, int]:
    line = text.count("\n", 0, start) + 1
    line_start = text.rfind("\n", 0, start) + 1
    return line, start - line_start + 1


class SensitiveWordsService:
    """Load local words and perform literal, case-insensitive matching."""

    def load_library(
        self,
        path: str | Path | None = None,
    ) -> SensitiveWordsLibrary:
        word_path = (
            Path(path).expanduser().resolve()
            if path is not None
            else default_sensitive_words_path()
        )
        return SensitiveWordsLibrary(
            path=word_path,
            words=_load_words(word_path),
        )

    def check_text(
        self,
        text: str,
        library: SensitiveWordsLibrary,
    ) -> SensitiveCheckResult:
        lowered_text = text.lower()
        matches: list[SensitiveMatch] = []
        for word in library.words:
            lowered_word = _normalized_word_key(word)
            start = 0
            while True:
                index = lowered_text.find(lowered_word, start)
                if index < 0:
                    break
                end = index + len(word)
                line, column = _line_and_column(text, index)
                matches.append(
                    SensitiveMatch(
                        word=word,
                        matched_text=text[index:end],
                        start=index,
                        end=end,
                        line=line,
                        column=column,
                    )
                )
                start = index + 1

        matches.sort(key=lambda match: (match.start, match.end, match.word))
        return SensitiveCheckResult(
            word_count=len(library.words),
            matches=tuple(matches),
        )

    def check(
        self,
        text: str,
        path: str | Path | None = None,
    ) -> SensitiveCheckResult:
        return self.check_text(text, self.load_library(path))

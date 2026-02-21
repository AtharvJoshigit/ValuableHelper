from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import AsyncIterator, Iterator, Optional

from engine.schemas.response import AgentResponse



# ---------------------------------------------------------------------------
# Streaming extractor (sync)
# ---------------------------------------------------------------------------

@dataclass
class StreamingJsonTextExtractor:
    """
    Feed raw string chunks from a streaming JSON response.
    Yields only the incremental response_text content.
    """

    _buffer: str = field(default="", init=False)
    _in_response_text: bool = field(default=False, init=False)
    _key_pattern: re.Pattern = field(
        default_factory=lambda: re.compile(r'"response_text"\s*:\s*"'),
        init=False,
    )
    _prev_text_len: int = field(default=0, init=False)
    _complete: bool = field(default=False, init=False)

    def feed(self, chunk: str) -> Iterator[str]:
        """
        Feed a raw chunk from the stream.
        Yields user-facing text fragments (zero or more per call).
        """
        if not chunk:
            return

        self._buffer += chunk

        if not self._in_response_text:
            match = self._key_pattern.search(self._buffer)
            if match:
                self._in_response_text = True
                self._prev_text_len = 0

        if self._in_response_text:
            extracted = self._extract_partial_string_value()
            if extracted and len(extracted) > self._prev_text_len:
                new_text = extracted[self._prev_text_len:]
                yield new_text
                self._prev_text_len = len(extracted)

    def finalize(self) -> Optional[AgentResponse]:
        """
        Call after the stream ends. Parses the complete JSON buffer
        into an AgentResponse. Returns None if parsing fails.
        """
        self._complete = True
        try:
            data = json.loads(self._buffer)
            return AgentResponse.model_validate(data)
        except (json.JSONDecodeError, Exception):
            return None

    def get_raw_buffer(self) -> str:
        """Return the accumulated raw JSON string."""
        return self._buffer

    def _extract_partial_string_value(self) -> Optional[str]:
        """
        Extract the current content of "response_text" from the partial
        JSON buffer, handling escaped characters.
        """
        match = self._key_pattern.search(self._buffer)
        if not match:
            return None

        start = match.end()
        result: list[str] = []
        i = start
        buf = self._buffer

        while i < len(buf):
            ch = buf[i]

            if ch == "\\" and i + 1 < len(buf):
                next_ch = buf[i + 1]
                escape_map = {
                    '"': '"',
                    "\\": "\\",
                    "/": "/",
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                    "b": "\b",
                    "f": "\f",
                }

                if next_ch in escape_map:
                    result.append(escape_map[next_ch])
                    i += 2
                    continue
                elif next_ch == "u" and i + 5 < len(buf):
                    hex_str = buf[i + 2 : i + 6]
                    try:
                        result.append(chr(int(hex_str, 16)))
                        i += 6
                        continue
                    except ValueError:
                        pass

                break

            elif ch == '"':
                break

            else:
                result.append(ch)
                i += 1

        return "".join(result) if result else None


# ---------------------------------------------------------------------------
# Streaming extractor (async) - instance-based, thread-safe
# ---------------------------------------------------------------------------

@dataclass
class AsyncStreamResult:
    """
    Holds the result of an async stream extraction.
    """

    parsed_response: Optional[AgentResponse] = field(default=None, init=False)
    raw_buffer: str = field(default="", init=False)
    _extractor: StreamingJsonTextExtractor = field(
        default_factory=StreamingJsonTextExtractor,
        init=False,
    )

    async def extract(self, stream: AsyncIterator) -> AsyncIterator[str]:
        """
        Async generator that yields user-facing response_text fragments.
        After iteration completes, self.parsed_response is populated.
        """
        async for chunk in stream:
            text_chunk = ""

            if hasattr(chunk, "text") and chunk.text:
                text_chunk = chunk.text
            elif isinstance(chunk, str):
                text_chunk = chunk

            for fragment in self._extractor.feed(text_chunk):
                yield fragment

        self.parsed_response = self._extractor.finalize()
        self.raw_buffer = self._extractor.get_raw_buffer()


# ---------------------------------------------------------------------------
# Sync helper - instance-based, thread-safe
# ---------------------------------------------------------------------------

@dataclass
class SyncStreamResult:
    """
    Sync counterpart of AsyncStreamResult.
    """

    parsed_response: Optional[AgentResponse] = field(default=None, init=False)
    raw_buffer: str = field(default="", init=False)
    _extractor: StreamingJsonTextExtractor = field(
        default_factory=StreamingJsonTextExtractor,
        init=False,
    )

    def extract(self, stream: Iterator) -> Iterator[str]:
        """
        Sync generator that yields user-facing response_text fragments.
        After iteration completes, self.parsed_response is populated.
        """
        for chunk in stream:
            text_chunk = ""

            if hasattr(chunk, "text") and chunk.text:
                text_chunk = chunk.text
            elif isinstance(chunk, str):
                text_chunk = chunk

            yield from self._extractor.feed(text_chunk)

        self.parsed_response = self._extractor.finalize()
        self.raw_buffer = self._extractor.get_raw_buffer()


# ---------------------------------------------------------------------------
# Backwards-compatible free functions (deprecated)
# ---------------------------------------------------------------------------

async def extract_text_from_async_stream(
    stream: AsyncIterator,
) -> AsyncIterator[str]:
    """
    Deprecated:
    Use AsyncStreamResult().extract(stream) instead.
    """
    extractor = StreamingJsonTextExtractor()

    async for chunk in stream:
        text_chunk = ""

        if hasattr(chunk, "text") and chunk.text:
            text_chunk = chunk.text
        elif isinstance(chunk, str):
            text_chunk = chunk

        for fragment in extractor.feed(text_chunk):
            yield fragment

    extract_text_from_async_stream.last_parsed_response = extractor.finalize()
    extract_text_from_async_stream.last_raw_buffer = extractor.get_raw_buffer()


def extract_text_from_sync_stream(
    stream: Iterator,
) -> Iterator[str]:
    """
    Deprecated:
    Use SyncStreamResult().extract(stream) instead.
    """
    extractor = StreamingJsonTextExtractor()

    for chunk in stream:
        text_chunk = ""

        if hasattr(chunk, "text") and chunk.text:
            text_chunk = chunk.text
        elif isinstance(chunk, str):
            text_chunk = chunk

        yield from extractor.feed(text_chunk)

    extract_text_from_sync_stream.last_parsed_response = extractor.finalize()
    extract_text_from_sync_stream.last_raw_buffer = extractor.get_raw_buffer()

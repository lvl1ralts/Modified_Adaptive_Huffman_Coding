"""Adaptive Huffman word-level encoder/decoder with NCW & NYT nodes.

Implements a simplified version of Vitter's algorithm suitable for
interactive chat compression.  The public API is intentionally small:

    >>> enc = AdaptiveHuffman()
    >>> data = enc.encode("hello world hello")
    >>> dec = AdaptiveHuffman()
    >>> text = dec.decode(data)
    >>> assert text == "hello world hello"

The implementation is **thread-safe** – a `threading.Lock` guards
modifications to the internal tree so concurrent encode / decode calls
on the same instance won't corrupt state.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

__all__ = [
    "AdaptiveHuffman",
]


class _BitWriter:
    """Accumulates individual bits and produces a bytes object."""

    def __init__(self) -> None:
        self._buffer: bytearray = bytearray()
        self._current: int = 0
        self._filled: int = 0  # number of bits filled in _current

    def add_bit(self, bit: bool) -> None:
        self._current = (self._current << 1) | int(bit)
        self._filled += 1
        if self._filled == 8:
            self._buffer.append(self._current)
            self._current = 0
            self._filled = 0

    def add_bits(self, bits: List[bool]) -> None:
        for b in bits:
            self.add_bit(b)

    def flush_to_byte(self) -> None:
        """Pad with zeros up to byte boundary and flush current byte."""
        if self._filled == 0:
            return
        self._current <<= 8 - self._filled
        self._buffer.append(self._current)
        self._current = 0
        self._filled = 0

    def add_uint16(self, value: int) -> None:
        """Write 16-bit unsigned integer in big-endian order at byte boundary."""
        self.flush_to_byte()
        self._buffer.extend(value.to_bytes(2, "big", signed=False))

    def add_bytes(self, data: bytes) -> None:
        self.flush_to_byte()
        self._buffer.extend(data)

    def get_data(self) -> bytes:
        self.flush_to_byte()
        return bytes(self._buffer)


class _BitReader:
    """Reads bits and byte-aligned data from a bytes object."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._byte_pos: int = 0
        self._bit_pos: int = 0  # 0–7, bit index inside current byte

    def _require_bits(self, n: int) -> None:
        remaining_bits = (len(self._data) - self._byte_pos) * 8 - self._bit_pos
        if n > remaining_bits:
            raise ValueError("Not enough bits left in stream")

    def read_bit(self) -> bool:
        self._require_bits(1)
        bit = (self._data[self._byte_pos] >> (7 - self._bit_pos)) & 1
        self._bit_pos += 1
        if self._bit_pos == 8:
            self._bit_pos = 0
            self._byte_pos += 1
        return bool(bit)

    def align_to_byte(self) -> None:
        if self._bit_pos == 0:
            return
        self._bit_pos = 0
        self._byte_pos += 1

    def read_uint16(self) -> int:
        self.align_to_byte()
        if self._byte_pos + 2 > len(self._data):
            raise ValueError("Unexpected end of stream while reading uint16")
        value = int.from_bytes(self._data[self._byte_pos : self._byte_pos + 2], "big")
        self._byte_pos += 2
        return value

    def read_bytes(self, length: int) -> bytes:
        self.align_to_byte()
        if self._byte_pos + length > len(self._data):
            raise ValueError("Unexpected end of stream while reading bytes")
        out = self._data[self._byte_pos : self._byte_pos + length]
        self._byte_pos += length
        return out

    def has_bits(self) -> bool:
        remaining_bits = (len(self._data) - self._byte_pos) * 8 - self._bit_pos
        return remaining_bits > 0


class _Node:
    """Single tree node."""

    __slots__ = (
        "symbol",
        "weight",
        "key",
        "left",
        "right",
        "parent",
        "is_nyt",
        "is_ncw",
    )

    def __init__(
        self,
        *,
        symbol: Optional[str] = None,
        weight: int = 0,
        key: int = 0,
        is_nyt: bool = False,
        is_ncw: bool = False,
    ) -> None:
        self.symbol: Optional[str] = symbol
        self.weight: int = weight
        self.key: int = key
        self.left: Optional["_Node"] = None
        self.right: Optional["_Node"] = None
        self.parent: Optional["_Node"] = None
        self.is_nyt: bool = is_nyt
        self.is_ncw: bool = is_ncw

    def is_leaf(self) -> bool:
        return self.left is None and self.right is None


class AdaptiveHuffman:
    """Thread-safe word-level adaptive Huffman encoder/decoder."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._leaves: Dict[str, _Node] = {}
        self._next_key: int = 3  # 0 reserved for dummy, 1 NYT, 2 NCW, 3 root

        # Create special leaves and root
        self._nyt = _Node(is_nyt=True, key=1)
        self._ncw = _Node(is_ncw=True, key=2)
        self._root = _Node(key=3, weight=0)
        self._root.left = self._nyt
        self._root.right = self._ncw
        self._nyt.parent = self._root
        self._ncw.parent = self._root

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def encode(self, text: str) -> bytes:
        """Compress *text* into a byte string representing a bit-stream."""
        with self._lock:
            return self._encode_internal(text)

    def decode(self, data: bytes) -> str:
        """Decompress *data* produced by `encode()` back to the original text."""
        with self._lock:
            return self._decode_internal(data)

    # ------------------------------------------------------------------
    # Internal helpers – all called WITH the lock already held.
    # ------------------------------------------------------------------

    def _encode_internal(self, text: str) -> bytes:
        writer = _BitWriter()
        words = text.split(" ") if text else []
        for idx, word in enumerate(words):
            if idx != 0:
                self._encode_word(" ", writer)  # separator symbol
            self._encode_word(word, writer)
        return writer.get_data()

    def _encode_word(self, word: str, writer: _BitWriter) -> None:
        new_word = word not in self._leaves
        # Step 1: output codeword (existing or NCW)
        target_node = self._leaves.get(word, self._ncw)
        path = self._path_to_node(target_node)
        writer.add_bits(path)

        # Step 2: if new word, write raw bytes length + data and insert into tree
        if new_word:
            # Align to byte boundary to simplify reader
            writer.flush_to_byte()
            raw = word.encode()
            if len(raw) >= 2 ** 16:
                raise ValueError("Word too long to encode (>65535 bytes)")
            writer.add_uint16(len(raw))
            writer.add_bytes(raw)
            self._insert_new_word(word)
            # Update NCW weight (already part of incrementWeight in insert)
        else:
            # Known word – just increment its node weight after emitting path
            self._increment_weight(self._leaves[word])

    # ------------------------------------------------------------------
    # Decoding helpers
    # ------------------------------------------------------------------
    def _decode_internal(self, data: bytes) -> str:
        reader = _BitReader(data)
        words: List[str] = []
        while reader.has_bits():
            word = self._decode_next_word(reader)
            if word == " ":
                continue  # separator
            words.append(word)
        return " ".join(words)

    def _decode_next_word(self, reader: _BitReader) -> str:
        node = self._root
        while not node.is_leaf():
            bit = reader.read_bit()
            node = node.right if bit else node.left  # type: ignore[assignment]

        if node.is_ncw:
            # NCW: read new word raw bytes, insert, return
            self._increment_weight(node)  # NCW weight++ (matches encoder order)
            reader.align_to_byte()
            length = reader.read_uint16()
            raw = reader.read_bytes(length)
            word = raw.decode()
            self._insert_new_word(word)
            return word
        elif node.is_nyt:
            # Should not appear in our encoding flow, but return empty string.
            return ""
        else:
            # Existing word
            self._increment_weight(node)
            return node.symbol or ""

    # ------------------------------------------------------------------
    # Tree manipulation
    # ------------------------------------------------------------------
    def _insert_new_word(self, word: str) -> None:
        """Replace NYT leaf by internal node + new leaf."""
        # Existing NYT gets converted to internal parent of (new NYT, new word)
        new_word_leaf = _Node(symbol=word, weight=0, key=self._next_key)
        self._next_key += 1

        new_nyt = _Node(is_nyt=True, key=self._next_key)
        self._next_key += 1

        internal = self._nyt
        internal.is_nyt = False  # it becomes internal
        internal.left = new_nyt
        internal.right = new_word_leaf
        new_nyt.parent = internal
        new_word_leaf.parent = internal

        # Register new structures
        self._leaves[word] = new_word_leaf
        self._nyt = new_nyt

        # Weight update – start at new_word_leaf (weight 0) and bubble up
        self._increment_weight(new_word_leaf)

    def _path_to_node(self, node: _Node) -> List[bool]:
        path: List[bool] = []
        current = node
        while current is not self._root:
            parent = current.parent
            if parent is None:
                raise RuntimeError("Node has no parent – corrupted tree")
            path.append(parent.right is current)
            current = parent
        path.reverse()
        return path

    # -------------------- weight maintenance -----------------------
    def _increment_weight(self, node: _Node) -> None:
        while node is not None:
            # Find highest-key node in same weight block
            highest = self._find_highest_node_in_block(node)
            if highest is not node and node.parent is not highest and highest.parent is not node:
                self._swap_nodes(node, highest)
            node.weight += 1
            node = node.parent

    def _find_highest_node_in_block(self, node: _Node) -> _Node:
        """Return highest-key node (not in `node`'s subtree) with same weight."""
        target_weight = node.weight
        highest: Optional[_Node] = node
        stack = [self._root]
        while stack:
            cur = stack.pop()
            if cur.weight == target_weight and cur.key > highest.key and not self._is_ancestor(cur, node):
                highest = cur
            if cur.left:
                stack.append(cur.left)
            if cur.right:
                stack.append(cur.right)
        return highest

    def _is_ancestor(self, anc: _Node, descendant: _Node) -> bool:
        current = descendant.parent
        while current is not None:
            if current is anc:
                return True
            current = current.parent
        return False

    def _swap_nodes(self, a: _Node, b: _Node) -> None:
        """Swap positions of nodes *a* and *b* in the tree (parents & children)."""
        if a is b:
            return
        a_parent, b_parent = a.parent, b.parent
        if a_parent is None or b_parent is None:
            return  # don't swap root

        # Determine which child position each node occupies
        def _replace_child(parent: _Node, old: _Node, new: _Node) -> None:
            if parent.left is old:
                parent.left = new
            elif parent.right is old:
                parent.right = new
            else:
                raise RuntimeError("Child not found when swapping nodes")

        _replace_child(a_parent, a, b)
        _replace_child(b_parent, b, a)
        a.parent, b.parent = b_parent, a_parent

    # ------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover – debug aid only
        lines: List[str] = []
        stack = [(self._root, 0)]
        while stack:
            node, depth = stack.pop()
            indent = "  " * depth
            if node.is_ncw:
                label = "<NCW>"
            elif node.is_nyt:
                label = "<NYT>"
            elif node.symbol == " ":
                label = "<SPACE>"
            else:
                label = node.symbol or "?"
            lines.append(f"{indent}{label} w={node.weight} k={node.key}")
            if node.right:
                stack.append((node.right, depth + 1))
            if node.left:
                stack.append((node.left, depth + 1))
        return "\n".join(lines) 
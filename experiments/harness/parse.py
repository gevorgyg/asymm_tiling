"""Parse the markdown stats output of `./asymm`.

Produces a typed Metrics dataclass. Also handles the `--- UNUSED OPTIONS ---`
header that the binary emits before the tables.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class CacheStats:
    hit_rate: float = 0.0
    tag_lookups: int = 0
    line_fills: int = 0
    evicts: int = 0
    writebacks: int = 0
    bytes_in: int = 0     # bytes filled into this level from below
    bytes_out: int = 0    # bytes pushed down (writebacks + write-through)


@dataclass
class DramStats:
    bytes_read: int = 0
    bytes_written: int = 0


@dataclass
class PrngStats:
    generates: int = 0
    regenerates: int = 0


@dataclass
class PrngFifoStats:
    starts: int = 0
    stops: int = 0
    reads: int = 0
    stalls: int = 0
    stall_cycles: int = 0
    generates: int = 0


@dataclass
class Metrics:
    l1: CacheStats = field(default_factory=CacheStats)
    l2: CacheStats = field(default_factory=CacheStats)
    dram: DramStats = field(default_factory=DramStats)
    cycles: int = 0
    prng: Optional[PrngStats] = None
    prng_fifo: Optional[PrngFifoStats] = None
    unused_options: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Metrics":
        # Missing keys (caches written before a field existed) fall back to
        # dataclass defaults, so old results.json files keep loading.
        return cls(
            l1=CacheStats(**d["l1"]),
            l2=CacheStats(**d["l2"]),
            dram=DramStats(**d.get("dram") or {}),
            cycles=d["cycles"],
            prng=PrngStats(**d["prng"]) if d.get("prng") else None,
            prng_fifo=PrngFifoStats(**d["prng_fifo"]) if d.get("prng_fifo") else None,
            unused_options=list(d.get("unused_options", [])),
        )


def _parse_tables(text: str):
    """Yield (header_cells, data_rows) for each markdown table block."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("|") and line.endswith("|"):
            header = [c.strip() for c in line.strip("|").split("|")]
            sep = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if not (sep.startswith("|") and "---" in sep):
                i += 1
                continue
            i += 2
            rows: list[list[str]] = []
            while i < len(lines):
                rl = lines[i].strip()
                if rl.startswith("|") and rl.endswith("|"):
                    rows.append([c.strip() for c in rl.strip("|").split("|")])
                    i += 1
                else:
                    break
            yield header, rows
        else:
            i += 1


def _parse_unused(text: str) -> list[str]:
    keys: list[str] = []
    in_block = False
    for line in text.splitlines():
        s = line.strip()
        if s == "--- UNUSED OPTIONS ---":
            in_block = True
        elif s == "--- END ---":
            in_block = False
        elif in_block and s.startswith("#"):
            keys.append(s.lstrip("#").strip())
    return [k for k in keys if k]


def parse_stdout(stdout: str) -> Metrics:
    m = Metrics(unused_options=_parse_unused(stdout))

    for header, rows in _parse_tables(stdout):
        tag = header[0] if header else ""
        if tag == "Cache":
            # Column lookup by header name: robust to column additions.
            col = {name: i for i, name in enumerate(header)}
            for row in rows:
                stats = CacheStats(
                    hit_rate=float(row[col["Hit rate"]]),
                    tag_lookups=int(row[col["TagLookup"]]),
                    line_fills=int(row[col["LineFill"]]),
                    evicts=int(row[col["Evict"]]),
                    writebacks=int(row[col["Writeback"]]) if "Writeback" in col else 0,
                    bytes_in=int(row[col["BytesIn"]]) if "BytesIn" in col else 0,
                    bytes_out=int(row[col["BytesOut"]]) if "BytesOut" in col else 0,
                )
                if row[0] == "L1":
                    m.l1 = stats
                elif row[0] == "L2":
                    m.l2 = stats
        elif tag == "DRAM":
            m.dram = DramStats(
                bytes_read=int(rows[0][1]),
                bytes_written=int(rows[0][2]),
            )
        elif tag == "PRNG":
            m.prng = PrngStats(
                generates=int(rows[0][1]),
                regenerates=int(rows[0][2]),
            )
        elif tag == "PRNG FIFO":
            m.prng_fifo = PrngFifoStats(
                starts=int(rows[0][1]),
                stops=int(rows[0][2]),
                reads=int(rows[0][3]),
                stalls=int(rows[0][4]),
                stall_cycles=int(rows[0][5]),
                generates=int(rows[0][6]),
            )
        elif tag == "System":
            m.cycles = int(rows[0][1])

    return m

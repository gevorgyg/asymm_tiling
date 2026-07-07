"""Closed-form traffic predictions from Multiplication_by_a_Random_Matrix.pdf.

The paper's model: a fast memory of M words holds one C block of shape
z x M/z while chunks of the inputs stream through; every word crossing the
fast-memory boundary is counted. "Reads" = words moved in, "writes" = words
moved out (mn total, one per C element).

Mapping onto this simulator (the paper's cheap matrix is A; ours is B, so
the tile that stretches is the *column* dimension):

    fast memory        = L1
    reads              = L1 BytesIn
    writes             = L1 BytesOut
    z x M/z C block    = TILE_M x TILE_N   (M = TILE_M*TILE_N C-words)
    rho                = B_PRECISION / A_PRECISION
    optimum            = T_N / T_M = 1/rho

Per C block the paper reads `rho*z*k + k*(M/z) + M` words. In bytes and our
tile variables that totals, over all (m/T_M)*(n/T_N) blocks:

    reads_bytes  = m*n*k * (A_p/T_N + B_p/T_M) + m*n*C_p
    writes_bytes = m*n*C_p

The word model ignores cache-line granularity; the line-aware variant rounds
each distinct row-segment touch up to whole lines, which matters when a tile
row is narrower than a line (small T_N x B_p).
"""

import math


def _row_lines_bytes(segment_bytes: int, line: int) -> int:
    """Bytes actually moved for one row segment, rounded up to whole lines."""
    return line * math.ceil(segment_bytes / line)


def reads_bytes(m: int, n: int, k: int, t_m: int, t_n: int,
                a_p: int, b_p: int, c_p: int) -> float:
    """Paper's read traffic (bytes into fast memory), word granularity."""
    return m * n * k * (a_p / t_n + b_p / t_m) + m * n * c_p


def reads_bytes_line_aware(m: int, n: int, k: int, t_m: int, t_n: int,
                           a_p: int, b_p: int, c_p: int, line: int) -> float:
    """Read traffic with every row-segment touch rounded up to whole lines."""
    blocks = (m // t_m) * (n // t_n)
    a = t_m * _row_lines_bytes(k * a_p, line)      # A strip: T_M rows of k elems
    b = k * _row_lines_bytes(t_n * b_p, line)      # B strip: k rows of T_N elems
    c = t_m * _row_lines_bytes(t_n * c_p, line)    # C block: T_M rows of T_N elems
    return blocks * (a + b + c)


def writes_bytes(m: int, n: int, c_p: int) -> float:
    """Paper's write traffic: each C element leaves fast memory exactly once."""
    return m * n * c_p


def writes_bytes_line_aware(m: int, n: int, t_m: int, t_n: int,
                            c_p: int, line: int) -> float:
    blocks = (m // t_m) * (n // t_n)
    return blocks * t_m * _row_lines_bytes(t_n * c_p, line)


def optimal_ratio(rho: float) -> float:
    """Predicted optimal T_N/T_M."""
    return 1.0 / rho


def savings_vs_square(rho: float) -> float:
    """Paper's asymptotic read ratio optimal/square: 2*sqrt(rho)/(1+rho)."""
    return 2.0 * math.sqrt(rho) / (1.0 + rho)

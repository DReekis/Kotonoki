import time
import os
import uuid

_last_v7_timestamp = 0
_v7_sequence = 0

def generate_uuid7() -> str:
    """
    Generate a monotonic RFC 9562 compliant UUIDv7 as a standard 36-char string.
    UUIDv7 encodes a 48-bit millisecond timestamp, 4-bit version (0b0111),
    12-bit sequence counter for monotonicity within the same ms,
    2-bit variant (0b10), and 62 random bits.
    """
    global _last_v7_timestamp, _v7_sequence
    
    current_ms = int(time.time() * 1000)
    
    if current_ms > _last_v7_timestamp:
        _last_v7_timestamp = current_ms
        _v7_sequence = int.from_bytes(os.urandom(2), "big") & 0xFFF
    else:
        # Same millisecond or clock skew: increment sequence
        _v7_sequence = (_v7_sequence + 1) & 0xFFF
        current_ms = _last_v7_timestamp

    # 48-bit timestamp
    time_high = (current_ms >> 16) & 0xFFFFFFFF
    time_mid = current_ms & 0xFFFF
    
    # 4-bit version (7) + 12-bit sequence
    time_hi_and_ver = (0x7 << 12) | (_v7_sequence & 0x0FFF)
    
    # 2-bit variant (0b10) + 6-bit clock_seq_hi + 8-bit clock_seq_low
    rand_bytes = os.urandom(8)
    clk_seq_hi_res = (0x2 << 6) | (rand_bytes[0] & 0x3F)
    clk_seq_low = rand_bytes[1]
    
    node = int.from_bytes(rand_bytes[2:], "big")
    
    return str(uuid.UUID(fields=(
        time_high,
        time_mid,
        time_hi_and_ver,
        clk_seq_hi_res,
        clk_seq_low,
        node
    )))

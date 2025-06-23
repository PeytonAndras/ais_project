"""
AIS Protocol Package - AIS Message Encoding and NMEA Generation
===============================================================
"""

from .ais_encoding import (
    sixbit_to_char,
    char_to_sixbit,
    compute_checksum,
    build_ais_payload,
    create_nmea_sentence
)

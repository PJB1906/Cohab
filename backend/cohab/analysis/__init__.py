"""Cohab v2 analysis package (W4 learning and calibration, W5 simulation).

Everything here is pure computation over plain records and NumPy arrays: no
FastAPI, no database. `reproduce.py` is the only module that touches
Postgres or the filesystem, so every result can be regenerated from one
command (`make reproduce`).
"""

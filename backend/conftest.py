"""Pytest configuration.

Ensures the backend/ directory (which contains the ``app`` package) is on
sys.path so tests can do ``from app.engine import ...`` regardless of the
directory pytest is invoked from.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

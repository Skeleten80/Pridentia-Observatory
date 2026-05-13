"""Pytest configuration for Prudentia Observatory tests."""
import os

# Prevent Qt from trying to connect to a display in headless environments
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#!/usr/bin/env python3
"""Backward-compatible validator entry point."""

from project_memory import main


if __name__ == "__main__":
    raise SystemExit(main(["validate"]))

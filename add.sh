#!/bin/bash
cd "$(dirname "$0")"
PYTHONPATH=src venv/bin/python src/add_target.py "$@"

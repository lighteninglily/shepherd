#!/bin/bash

# Exit on error
set -e

echo "=== Running Black ==="
python -m black .

echo -e "\n=== Running isort ==="
python -m isort .

echo -e "\n=== Running Flake8 ==="
python -m flake8 .

echo -e "\n=== Running Mypy ==="
python -m mypy .

echo -e "\n=== All checks passed! ==="

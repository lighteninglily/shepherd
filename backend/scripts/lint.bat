@echo off
echo === Running Black ===
python -m black .

echo.
echo === Running isort ===
python -m isort .

echo.
echo === Running Flake8 ===
python -m flake8 .

echo.
echo === Running Mypy ===
python -m mypy .

echo.
echo === All checks passed! ===
pause

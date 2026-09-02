#!/bin/bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build/lambda"
ZIP_PATH="$PROJECT_ROOT/build/portfolio-agent.zip"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Cleaning previous Lambda build..."
rm -rf "$BUILD_DIR"
rm -f "$ZIP_PATH"

mkdir -p "$BUILD_DIR"

echo "Installing Lambda dependencies..."
"$PYTHON_BIN" -m pip install \
    -r "$PROJECT_ROOT/requirements.txt" \
    -t "$BUILD_DIR" \
    --platform manylinux2014_x86_64 \
    --implementation cp \
    --python-version 3.13 \
    --only-binary=:all:

echo "Copying application code..."
cp -R "$PROJECT_ROOT/src/." "$BUILD_DIR/"

echo "Removing development-only files..."
find "$BUILD_DIR" \
    -type d \
    -name "__pycache__" \
    -prune \
    -exec rm -rf {} +

find "$BUILD_DIR" \
    -type f \
    \( -name "*.pyc" -o -name ".DS_Store" \) \
    -delete

echo "Creating deployment ZIP..."
(
    cd "$BUILD_DIR"
    zip -qr "$ZIP_PATH" .
)

echo "Validating Lambda imports..."
PYTHONPATH="$BUILD_DIR" "$PYTHON_BIN" -c \
    'from portfolio_agent.lambda_handler import lambda_handler'

echo
echo "Lambda package created:"
echo "$ZIP_PATH"

echo
echo "Package size:"
du -h "$ZIP_PATH"

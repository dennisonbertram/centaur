#!/usr/bin/env bash
set -euo pipefail

MANIM_VERSION="${MANIM_VERSION:-0.20.1}"
missing=0

check_cmd() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    printf '[ok] %s\n' "$name"
  else
    printf '[missing] %s\n' "$name"
    missing=1
  fi
}

bootstrap_manim() {
  printf '[bootstrap] installing manim %s with uv\n' "$MANIM_VERSION"
  if ! uv tool install --upgrade "manim==${MANIM_VERSION}"; then
    missing=1
  fi
}

printf 'Checking Manim video prerequisites...\n'

check_cmd uv
check_cmd ffmpeg
check_cmd pkg-config

if command -v latex >/dev/null 2>&1; then
  printf '[ok] latex\n'
elif command -v pdflatex >/dev/null 2>&1; then
  printf '[ok] pdflatex\n'
else
  printf '[missing] latex or pdflatex\n'
  missing=1
fi

if ! command -v manim >/dev/null 2>&1; then
  bootstrap_manim
fi

manim_ready=0

if command -v manim >/dev/null 2>&1; then
  if manim --version >/dev/null 2>&1; then
    printf '[ok] manim\n'
    manim_ready=1
  else
    printf '[missing] manim runtime\n'
    missing=1
  fi

else
  printf '[missing] manim\n'
  missing=1
fi

if [ "$manim_ready" -eq 1 ]; then
  if manim checkhealth >/tmp/manim-checkhealth.log 2>&1; then
    printf '[ok] manim checkhealth\n'
  else
    printf '[missing] manim checkhealth\n'
    sed -n '1,120p' /tmp/manim-checkhealth.log >&2
    missing=1
  fi
fi

if [ "$missing" -ne 0 ]; then
  cat <<'EOF' >&2

The render path is still blocked. For an explicit video request, do not stop at
plan.md and script.py until you have tried setup.sh and one draft render. If the
build still fails here, report the missing native dependency and continue with the
script deliverables instead of claiming a finished video.
EOF
  exit 1
fi

printf '\nRender path is ready.\n'

#!/usr/bin/env bash
# Transcribe a voice message (OGG/OGG-Opus) using Groq Whisper (free).
# Usage: transcribe.sh <path-to-audio-file> [language]
# language: ar (Arabic) or en (English, default)
# Output: plain text transcription to stdout
set -euo pipefail

AUDIO_FILE="${1:-}"
LANG="${2:-}"

if [ -z "$AUDIO_FILE" ] || [ ! -f "$AUDIO_FILE" ]; then
  echo "Error: audio file not found: ${AUDIO_FILE}" >&2
  exit 1
fi

if [ -z "${GROQ_API_KEY:-}" ]; then
  echo "Error: GROQ_API_KEY not set" >&2
  exit 1
fi

ARGS=(-s "https://api.groq.com/openai/v1/audio/transcriptions"
  -H "Authorization: Bearer ${GROQ_API_KEY}"
  -F "file=@${AUDIO_FILE}"
  -F "model=whisper-large-v3-turbo"
  -F "response_format=text")

if [ -n "$LANG" ]; then
  ARGS+=(-F "language=${LANG}")
fi

curl "${ARGS[@]}"

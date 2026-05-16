#!/usr/bin/env bash
# Convert text to a WhatsApp-compatible OGG voice file using Piper TTS.
# Usage: speak.sh "text to speak" [lang]
# lang: en (default) | ar (Arabic — requires ar model to be downloaded)
# Output: path to the generated OGG file (ready to send via WhatsApp)
set -euo pipefail

TEXT="${1:-}"
LANG="${2:-en}"

if [ -z "$TEXT" ]; then
  echo "Error: no text provided" >&2
  exit 1
fi

MODEL_DIR="/data/.openclaw/workspace/skills/piper-tts/models"
OUTPUT_DIR="/data/.openclaw/media/outbound"
mkdir -p "$OUTPUT_DIR"
OUTPUT="${OUTPUT_DIR}/vio-tts-$(date +%s%N).ogg"

case "$LANG" in
  ar)  MODEL="${MODEL_DIR}/ar_JO-kareem-medium.onnx" ; RATE=22050 ;;
  *)   MODEL="${MODEL_DIR}/en_US-lessac-medium.onnx"  ; RATE=22050 ;;
esac

if [ ! -f "$MODEL" ]; then
  echo "Error: voice model not found: ${MODEL}" >&2
  echo "Download it first with the vio-voice download-model command." >&2
  exit 1
fi

echo "$TEXT" | piper -m "$MODEL" --output-raw | \
  ffmpeg -f s16le -ar "$RATE" -ac 1 -i pipe:0 \
    -c:a libopus -b:a 24k -ar 48000 "$OUTPUT" -y -loglevel error

echo "$OUTPUT"

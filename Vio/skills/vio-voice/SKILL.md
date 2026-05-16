---
name: vio-voice
description: Voice I/O for Vio over WhatsApp. Handles inbound voice messages (transcribe OGG → text via Groq Whisper) and outbound voice replies (text → OGG via Piper TTS → WhatsApp). Load when user sends a voice message or asks Vio to reply with voice. Supports English now; Arabic requires downloading the ar_JO-kareem model.
---

# Vio Voice

Gives Vio the ability to understand voice messages from Mazin and reply
with a spoken voice note on WhatsApp.

## Inbound — transcribe a voice message

When Mazin sends a voice message, openclaw delivers it as an `.ogg` file
under `/data/.openclaw/media/inbound/`.

**To transcribe:**

```bash
bash /data/.openclaw/skills/vio-voice/scripts/transcribe.sh <path-to-ogg> [ar|en]
```

- Uses Groq Whisper (`whisper-large-v3-turbo`) — free, fast.
- `GROQ_API_KEY` is read from the environment (already set).
- Outputs plain text to stdout.
- Pass `ar` as second argument for Arabic audio, `en` (or omit) for English.

**Full example:**

```bash
bash /data/.openclaw/skills/vio-voice/scripts/transcribe.sh \
  /data/.openclaw/media/inbound/9be15379-1171-4133-a20a-67ee0691bc88.ogg ar
```

After transcription, answer Mazin's question normally in the right language.

## Outbound — reply with a voice note

When Mazin asks for a voice reply or it makes sense to speak the answer:

**Step 1 — Generate OGG:**

```bash
bash /data/.openclaw/skills/vio-voice/scripts/speak.sh "Your reply text here" en
```

Returns the path to the generated `.ogg` file.

**Step 2 — Send via WhatsApp:**

Use the message tool with `asVoice: true` and the file path from Step 1.

```
action: send
channel: whatsapp
filePath: <path from speak.sh>
asVoice: true
```

## Language support

| Language | Model file | Status |
|----------|-----------|--------|
| English | `en_US-lessac-medium.onnx` | ✅ installed |
| Arabic | `ar_JO-kareem-medium.onnx` | ❌ not yet downloaded |

### Download Arabic model

```bash
cd /data/.openclaw/workspace/skills/piper-tts/models
wget -q https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx
wget -q https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx.json
```

After downloading, Arabic TTS will work automatically.

## Groq Whisper — supported audio formats

`.ogg`, `.mp3`, `.mp4`, `.wav`, `.m4a`, `.webm` — all work.
Maximum file size: 25 MB. WhatsApp voice notes are always well under this.

## Troubleshooting

| Error | Fix |
|-------|-----|
| `GROQ_API_KEY not set` | Check `.env` — key must be `GROQ_API_KEY=sk-...` |
| `voice model not found` | Download the model (see table above) |
| `ffmpeg: command not found` | `apt-get install -y ffmpeg` inside container |
| Transcription wrong language | Pass `ar` or `en` as second arg to transcribe.sh |

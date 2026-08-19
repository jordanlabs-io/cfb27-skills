#!/usr/bin/env python3
import json, sys
from faster_whisper import WhisperModel
wav, out = sys.argv[1], sys.argv[2]
m = WhisperModel("mobiuslabsgmbh/faster-whisper-large-v3-turbo", device="cpu", compute_type="int8")
segs, info = m.transcribe(wav, vad_filter=True, beam_size=5)
rows = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]
json.dump({"language": info.language, "duration": info.duration, "segments": rows},
          open(out, "w"), indent=1)
print(f"{len(rows)} segments -> {out}")

"""Local Sovereign-tier worker — processes transcription jobs with model_size='local+...'
entirely on-GPU ($0 cloud, audio never leaves the box). Runs as a SEPARATE process from
gemini_worker.py (which now skips local jobs). Start it the same way as the other workers
(bat / Task Scheduler) — this file never starts itself.

Pipeline: Pathumma (NECTEC ASR) -> ECAPA+spectral diarize -> Typhoon MoM, all local.
Each heavy stage runs in its own subprocess via experiments/run_local.py (REQUIRED on Windows:
ctranslate2 + torch + speechbrain in one interpreter hard-aborts).

For fast testing on long meetings, audio is trimmed to the first LOCAL_MAX_SEC seconds
(default 900 = 15 min). Set LOCAL_MAX_SEC=0 to process the whole file.
"""
import json
import logging
import os
import re
import subprocess
import sys
import time
import threading
import tempfile

import sqlalchemy as sa

from app.database import SessionLocal
from app.models.audio import AudioFile, AudioStatus
from app.models.transcription import (
    Transcription, TranscriptionSegment, TranscriptionStatus, TranscriptionGroup,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [local_worker] %(levelname)s %(message)s")
logger = logging.getLogger("local_worker")

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_LOCAL = os.path.join(HERE, "experiments", "run_local.py")
MAX_SEC = int(os.environ.get("LOCAL_MAX_SEC", "900"))  # 15 min default; 0 = full file

# model_size prefix -> which local ASR. 'local' (legacy) = pathumma. e.g. 'local_qwen+gemini' -> qwen.
_ASR_MAP = {"local": "pathumma", "local_pathumma": "pathumma", "local_qwen": "qwen", "local_monsoon": "monsoon"}
_ASR_LABEL = {"pathumma": "Pathumma (NECTEC)", "qwen": "Qwen3-ASR", "monsoon": "Monsoon"}


def _asr_from_model_size(model_size):
    head = (model_size or "").split("+")[0]
    return _ASR_MAP.get(head, "pathumma")


def _is_owner_tag(s):
    return s.startswith("(ผู้รับผิดชอบ") or s.startswith("[ผู้รับผิดชอบ") or s.startswith("（ผู้รับผิดชอบ")


def _split_mom_sections(mom_md):
    """Split MoM markdown into {section_title: [item, ...]} for '### ' headers.
    An item is a bulleted line OR (in สิ่งที่ต้องทำ) a line led by a '(ผู้รับผิดชอบ: ...)' tag,
    since the MoM model sometimes drops the leading dash."""
    sections, cur = {}, None
    for line in (mom_md or "").split("\n"):
        s = line.strip()
        if s.startswith("###"):
            cur = s.lstrip("# ").strip()
            sections[cur] = []
        elif cur is not None and s:
            if s[:1] in "-*•":
                item = s.lstrip("-*• ").strip()
            elif _is_owner_tag(s):
                item = s
            else:
                continue
            if item:
                sections[cur].append(item)
    return sections


# Leading owner tag the MoM model is asked to emit, e.g. "(ผู้รับผิดชอบ: Speaker 2) task"
_OWNER_RE = re.compile(r"^\s*[\(\[]\s*ผู้รับผิดชอบ\s*[:：]\s*(.+?)\s*[\)\]]\s*")


def _parse_action_bullet(text):
    """Split an action bullet into (task, owner). Owner comes from a leading
    '(ผู้รับผิดชอบ: ...)' tag if present, else '-'."""
    m = _OWNER_RE.match(text or "")
    if m:
        owner = m.group(1).strip()
        task = text[m.end():].strip()
        if owner in ("ไม่ระบุ", "-", "", "ไม่ทราบ", "N/A"):
            owner = "-"
        return (task or text.strip()), owner
    return (text or "").strip(), "-"


def mom_actions_to_table(mom_md):
    """Rewrite bullets under '### สิ่งที่ต้องทำ' into the markdown table MomModal/docx expect
    (| ลำดับ | รายละเอียด | กำหนดการ | ผู้รับผิดชอบ |). Free + deterministic, no model call.
    Owner column comes from each bullet's '(ผู้รับผิดชอบ: ...)' tag."""
    lines = (mom_md or "").split("\n")
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        out.append(line)
        if line.strip().startswith("###") and "สิ่งที่ต้องทำ" in line:
            i += 1
            block = []
            while i < n and not lines[i].strip().startswith("###"):
                block.append(lines[i])
                i += 1
            bullets = []
            for b in block:
                s = b.strip()
                if not s:
                    continue
                if s[:1] in "-*•":
                    s = s.lstrip("-*• ").strip()
                elif not _is_owner_tag(s):
                    continue
                if s:
                    bullets.append(s)
            if bullets:
                out.append("")
                out.append("| ลำดับ | รายละเอียด | กำหนดการ | ผู้รับผิดชอบ |")
                out.append("|------|-----------|---------|------------|")
                for idx, b in enumerate(bullets, 1):
                    task, owner = _parse_action_bullet(b)
                    out.append(f"| {idx} | {task} | TBC | {owner} |")
                out.append("")
            else:
                out.extend(block)
            continue
        i += 1
    return "\n".join(out)


class _ProgressTicker:
    """Creep progress_percent from `lo` toward `hi` while the subprocess runs (own DB session)."""
    def __init__(self, transcription_id, lo, hi, message):
        self.tid, self.lo, self.hi, self.message = transcription_id, lo, hi, message
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def _run(self):
        pct = self.lo
        while not self._stop.wait(8):
            pct = min(self.hi, pct + 1)
            db = SessionLocal()
            try:
                t = db.query(Transcription).filter(Transcription.id == self.tid).first()
                if t and t.status == TranscriptionStatus.in_progress:
                    t.progress_percent = pct
                    t.status_message = self.message
                    db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()

    def __exit__(self, *a):
        self._stop.set()
        self._thread.join(timeout=2)


def apply_mom_fields(t, mom, speakers_list, duration):
    """Set all MoM-derived fields on `t` from the MoM markdown: structured JSON
    (topics/key_decisions/action_items with owner) + summary + mom_full (สิ่งที่ต้องทำ as table).
    Reused by write_local_result and the re-MoM path so both stay identical."""
    secs = _split_mom_sections(mom)
    t.topics = json.dumps(secs.get("ประเด็นที่พูดคุย", []), ensure_ascii=False)
    t.key_decisions = json.dumps(secs.get("มติที่ประชุม", []), ensure_ascii=False)
    actions = []
    for b in secs.get("สิ่งที่ต้องทำ", []):
        task, owner = _parse_action_bullet(b)
        actions.append({"task": task, "deadline": "TBC", "owner": owner})
    t.action_items = json.dumps(actions, ensure_ascii=False)
    overview = secs.get("สรุปภาพรวม", [])
    if overview:
        t.summary_short = overview[0]

    mom_tbl = mom_actions_to_table(mom)
    auto_title = (t.audio_file.original_filename or "การประชุม")
    t.auto_title = auto_title
    t.summary = mom_tbl

    mom_meta = "### ข้อมูลการประชุม\n"
    mom_meta += f"- **หัวข้อ:** {auto_title}\n"
    mom_meta += f"- **วันที่:** {t.created_at.strftime('%d/%m/%Y %H:%M')}\n"
    mom_meta += f"- **ความยาวที่ประมวลผล:** {int(duration // 60)} นาที {int(duration % 60)} วินาที"
    if MAX_SEC:
        mom_meta += f" (ตัดมา {MAX_SEC // 60} นาทีแรกเพื่อทดสอบ)"
    mom_meta += f"\n- **ผู้เข้าร่วม:** {', '.join(speakers_list)}\n"
    asr_label = _ASR_LABEL.get(_asr_from_model_size(t.model_size), "Pathumma")
    mom_meta += f"- **โมเดล:** Local Sovereign ({asr_label} ASR + ECAPA/spectral + Typhoon MoM, $0 cloud)\n"
    t.mom_full = mom_meta + "\n" + mom_tbl


def write_local_result(db, t, outdir, elapsed):
    """Parse run_local.py output (transcript.json + mom.md) and write it onto Transcription `t`.
    Shared by the worker (process_local) and the manual ingest path so both produce identical DB rows.
    """
    transcript_path = os.path.join(outdir, "transcript.json")
    mom_path = os.path.join(outdir, "mom.md")
    if not os.path.exists(transcript_path):
        raise RuntimeError("local pipeline produced no transcript.json")

    data = json.load(open(transcript_path, encoding="utf-8"))
    segments = data.get("segments", [])

    all_text = []
    speakers_list, seen_spk = [], set()
    for i, seg in enumerate(segments):
        spk = seg.get("speaker", "Speaker 1")
        db.add(TranscriptionSegment(
            transcription_id=t.id,
            segment_index=i,
            start_time=seg.get("start", 0),
            end_time=seg.get("end", 0),
            text=seg.get("text", ""),
            speaker=spk,
        ))
        all_text.append(seg.get("text", ""))
        if spk not in seen_spk:
            speakers_list.append(spk)
            seen_spk.add(spk)

    duration = max((seg.get("end", 0) for seg in segments), default=0)
    mom = ""
    if os.path.exists(mom_path):
        mom = open(mom_path, encoding="utf-8").read().strip()

    apply_mom_fields(t, mom, speakers_list, duration)

    t.full_text = " ".join(all_text).strip()
    t.detected_language = "th"
    t.status = TranscriptionStatus.completed
    t.progress_percent = 100
    t.status_message = f"เสร็จสิ้น (Local, {elapsed:.0f}s)"
    t.processing_time_seconds = elapsed
    t.audio_file.status = AudioStatus.completed

    # Local pipeline = no cloud cost
    t.deepgram_cost_usd = 0
    t.gemini_cost_usd = 0
    t.total_cost_usd = 0
    t.deepgram_duration_sec = duration
    db.commit()
    logger.info("#%d Local done in %.0fs (%d segments, %d speakers)",
                t.id, elapsed, len(segments), len(speakers_list))
    return len(segments), len(speakers_list)


def process_local(transcription_id):
    db = SessionLocal()
    tmpdir = None
    try:
        t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if not t:
            return

        t.status = TranscriptionStatus.in_progress
        t.progress_percent = 5
        t.status_message = "เตรียมไฟล์ (Local Sovereign)..."
        db.commit()

        audio_path = os.path.abspath(t.audio_file.file_path)
        tmpdir = tempfile.mkdtemp(prefix=f"local_{transcription_id}_")
        start_time = time.time()

        asr = _asr_from_model_size(t.model_size)
        cmd = [
            sys.executable, RUN_LOCAL,
            "--audio", audio_path,
            "--asr", asr,
            "--diarize",
            "--mom",
            "--outdir", tmpdir,
        ]
        if MAX_SEC and MAX_SEC > 0:
            cmd += ["--max-sec", str(MAX_SEC)]

        trim_note = f" ({MAX_SEC // 60} นาทีแรก)" if MAX_SEC else ""
        logger.info("#%d Running local pipeline%s: %s", transcription_id, trim_note, " ".join(cmd))

        with _ProgressTicker(transcription_id, 10, 95, f"ถอดเสียง+สรุปด้วยโมเดลในเครื่อง (Local){trim_note}..."):
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            tail = (r.stderr or r.stdout or "")[-500:]
            raise RuntimeError(f"run_local.py failed (rc={r.returncode}): {tail}")

        elapsed = time.time() - start_time
        write_local_result(db, t, tmpdir, elapsed)

    except Exception as e:
        logger.exception("#%d Local failed: %s", transcription_id, e)
        db.rollback()
        t = db.query(Transcription).filter(Transcription.id == transcription_id).first()
        if t:
            t.status = TranscriptionStatus.failed
            t.status_message = f"ล้มเหลว (Local): {str(e)[:100]}"
            if t.audio_file:
                t.audio_file.status = AudioStatus.failed
            db.commit()
    finally:
        db.close()
        if tmpdir and os.path.isdir(tmpdir):
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    db = SessionLocal()
    pending = (
        db.query(Transcription)
        .filter(Transcription.status == TranscriptionStatus.pending)
        .filter(Transcription.model_size.like("local%"))
        .order_by(Transcription.created_at)
        .first()
    )
    pid = pending.id if pending else None
    db.close()
    if pid:
        logger.info("Processing local #%d", pid)
        process_local(pid)


def _get_code_mtime():
    latest = 0
    for f in os.listdir(HERE):
        if f.endswith(".py"):
            mt = os.path.getmtime(os.path.join(HERE, f))
            latest = max(latest, mt)
    return latest


if __name__ == "__main__":
    _start_mtime = _get_code_mtime()
    logger.info("local_worker started (MAX_SEC=%d)", MAX_SEC)
    while True:
        main()
        if _get_code_mtime() > _start_mtime:
            logger.info("Code changed, restarting local_worker...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        time.sleep(5)

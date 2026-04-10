import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, FileAudio } from 'lucide-react';
import { getGroups } from '../api';
import { getToken } from '../lib/auth';

export default function UploadPage() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [groups, setGroups] = useState([]);
  const [form, setForm] = useState({ group_id: '', diarization_model: 'deepgram', transcription_model: 'gemini' });
  const fileRef = useRef();
  const navigate = useNavigate();

  useEffect(() => {
    getGroups().then(g => {
      setGroups(g);
      const def = g.find(x => x.is_default);
      if (def) setForm(f => ({ ...f, group_id: String(def.id) }));
    });
  }, []);

  async function handleSubmit() {
    if (!file) return;
    setUploading(true);
    try {
      // Step 1: Upload
      const uploadForm = new FormData();
      uploadForm.append('file', file);
      const uploadRes = await fetch('/htmx/upload', { method: 'POST', body: uploadForm, headers: { Authorization: `Bearer ${getToken()}` } });
      const text = await uploadRes.text();
      const match = text.match(/audio\/(\d+)/);
      const redirect = uploadRes.headers.get('HX-Redirect');
      const audioId = match?.[1] || redirect?.match(/audio\/(\d+)/)?.[1];

      if (!audioId) { setUploading(false); return; }

      // Step 2: Start with config
      const startForm = new FormData();
      Object.entries(form).forEach(([k, v]) => startForm.append(k, v));
      const startRes = await fetch(`/api/audio/${audioId}/start`, { method: 'POST', body: startForm, headers: { Authorization: `Bearer ${getToken()}` } });

      // Navigate to transcription
      if (startRes.redirected) {
        navigate(new URL(startRes.url).pathname);
      } else {
        const startText = await startRes.text();
        const tMatch = startText.match(/transcriptions\/(\d+)/);
        if (tMatch) navigate(`/transcriptions/${tMatch[1]}`);
        else navigate('/');
      }
    } catch (err) {
      console.error(err);
      setUploading(false);
    }
  }

  return (
    <div className="flex items-center justify-center h-full">
      <div className="w-full max-w-lg p-8">
        <h2 className="text-xl font-semibold mb-2">อัพโหลดไฟล์เสียง</h2>
        <p className="text-sm text-[#9ca3af] mb-6">เลือกไฟล์ ตั้งค่า แล้วเริ่มถอดเสียงได้เลย</p>

        {/* Drop zone */}
        <div
          className={`border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer mb-5 ${
            dragOver ? 'border-[#2563eb] bg-[#eff6ff]' : file ? 'border-[#22c55e] bg-[#f0fdf4]' : 'border-[#d1d5db] hover:border-[#2563eb] hover:bg-[#fafafa]'
          }`}
          onClick={() => fileRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={e => { e.preventDefault(); setDragOver(false); if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); }}
        >
          {file ? (
            <div className="flex flex-col items-center gap-2">
              <FileAudio className="w-8 h-8 text-[#22c55e]" />
              <div className="text-sm font-medium text-[#374151]">{file.name}</div>
              <div className="text-xs text-[#9ca3af]">{(file.size / 1024 / 1024).toFixed(1)} MB</div>
              <button onClick={e => { e.stopPropagation(); setFile(null); }} className="text-xs text-[#9ca3af] hover:text-[#ef4444]">เปลี่ยนไฟล์</button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              <Upload className="w-8 h-8 text-[#9ca3af]" />
              <div className="text-sm text-[#374151]">ลากไฟล์มาวาง หรือคลิกเพื่อเลือก</div>
              <div className="text-xs text-[#9ca3af]">MP3, WAV, M4A, OGG, FLAC, MP4</div>
            </div>
          )}
          <input ref={fileRef} type="file" className="hidden" accept=".mp3,.wav,.m4a,.ogg,.flac,.webm,.mp4,.wma" onChange={e => { if (e.target.files[0]) setFile(e.target.files[0]); }} />
        </div>

        {/* Settings */}
        <div className="space-y-4 mb-6">
          <div>
            <label className="block text-sm font-medium mb-1.5">กลุ่ม</label>
            <select value={form.group_id} onChange={e => setForm({ ...form, group_id: e.target.value })}
              className="w-full px-3 py-2.5 border border-[#d1d5db] rounded-lg text-sm focus:outline-none focus:border-[#2563eb]">
              {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Diarization (แยกผู้พูด)</label>
            <select value={form.diarization_model} onChange={e => setForm({ ...form, diarization_model: e.target.value })}
              className="w-full px-3 py-2.5 border border-[#d1d5db] rounded-lg text-sm focus:outline-none focus:border-[#2563eb]">
              <option value="deepgram">Deepgram Nova-3 (API)</option>
              <option value="spectral">Spectral Clustering (Deepgram + Local GPU)</option>
              <option value="pyannote">Pyannote (Local GPU)</option>
              <option value="gemini">Gemini 2.5 Flash (API)</option>
              <option value="gpt">GPT-4o (API)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Transcription (ถอดคำ)</label>
            <select value={form.transcription_model} onChange={e => setForm({ ...form, transcription_model: e.target.value })}
              className="w-full px-3 py-2.5 border border-[#d1d5db] rounded-lg text-sm focus:outline-none focus:border-[#2563eb]">
              <option value="gemini">Gemini 2.5 Flash (API)</option>
            </select>
          </div>
        </div>

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={!file || uploading}
          className="w-full py-3 bg-[#2563eb] hover:bg-[#1d4ed8] disabled:bg-[#d1d5db] text-white rounded-lg text-sm font-medium transition-colors"
        >
          {uploading ? 'กำลังอัพโหลดและเริ่มถอดเสียง...' : 'เริ่มถอดเสียง'}
        </button>
      </div>
    </div>
  );
}

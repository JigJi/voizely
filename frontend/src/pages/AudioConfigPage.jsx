import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getGroups } from '../api';

export default function AudioConfigPage() {
  const { audioId } = useParams();
  const navigate = useNavigate();
  const [groups, setGroups] = useState([]);
  const [form, setForm] = useState({ group_id: '', diarization_model: 'deepgram', transcription_model: 'gemini' });

  useEffect(() => { getGroups().then(setGroups); }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    const formData = new FormData();
    Object.entries(form).forEach(([k, v]) => formData.append(k, v));
    const res = await fetch(`/api/audio/${audioId}/start`, { method: 'POST', body: formData });
    if (res.redirected) navigate(new URL(res.url).pathname);
    else navigate('/');
  }

  return (
    <div className="flex items-center justify-center h-full">
      <form onSubmit={handleSubmit} className="w-full max-w-md p-8">
        <h2 className="text-lg font-semibold mb-1">ตั้งค่าการถอดเสียง</h2>
        <p className="text-sm text-[#9ca3af] mb-6">เลือกโมเดลและกลุ่มก่อนเริ่มถอดเสียง</p>

        <label className="block text-sm font-medium mb-1.5">กลุ่ม</label>
        <select value={form.group_id} onChange={e => setForm({ ...form, group_id: e.target.value })}
          className="w-full px-3 py-2.5 border border-[#d1d5db] rounded-lg text-sm mb-4 focus:outline-none focus:border-[#2563eb]">
          {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
        </select>

        <label className="block text-sm font-medium mb-1.5">Diarization (แยกผู้พูด)</label>
        <select value={form.diarization_model} onChange={e => setForm({ ...form, diarization_model: e.target.value })}
          className="w-full px-3 py-2.5 border border-[#d1d5db] rounded-lg text-sm mb-4 focus:outline-none focus:border-[#2563eb]">
          <option value="deepgram">Deepgram Nova-3 (API)</option>
          <option value="pyannote">Pyannote (Local GPU)</option>
          <option value="gemini">Gemini 2.5 Flash (API)</option>
          <option value="gpt">GPT-4o (API)</option>
        </select>

        <label className="block text-sm font-medium mb-1.5">Transcription (ถอดคำ)</label>
        <select value={form.transcription_model} onChange={e => setForm({ ...form, transcription_model: e.target.value })}
          className="w-full px-3 py-2.5 border border-[#d1d5db] rounded-lg text-sm mb-6 focus:outline-none focus:border-[#2563eb]">
          <option value="gemini">Gemini 2.5 Flash (API)</option>
        </select>

        <button type="submit" className="w-full py-3 bg-[#2563eb] hover:bg-[#1d4ed8] text-white rounded-lg text-sm font-medium transition-colors">
          เริ่มถอดเสียง
        </button>
      </form>
    </div>
  );
}

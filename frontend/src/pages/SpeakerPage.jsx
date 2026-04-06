import { useState, useEffect } from 'react';
import { Trash2, Plus } from 'lucide-react';
import { getSpeakers, createSpeaker, updateSpeaker, deleteSpeaker } from '../api';
import Modal from '../components/Modal';
import { notify } from '../components/Notification';

export default function SpeakerPage() {
  const [speakers, setSpeakers] = useState([]);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [showNew, setShowNew] = useState(false);

  useEffect(() => { load(); }, []);
  async function load() { setSpeakers(await getSpeakers()); }

  async function handleEdit(id, field, value) {
    try {
      await updateSpeaker(id, { [field]: value });
      load();
    } catch (e) {
      notify(e.message || 'ชื่อซ้ำ กรุณาใช้ชื่ออื่น', 'error');
      load();
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    await deleteSpeaker(deleteTarget.id);
    setDeleteTarget(null);
    notify('ลบแล้ว');
    load();
  }

  async function handleCreate(nickname) {
    if (!nickname) return;
    try {
      await createSpeaker({ nickname });
      setShowNew(false);
      notify(`เพิ่ม "${nickname}" แล้ว`);
      load();
    } catch (e) {
      notify(e.message || 'ชื่อซ้ำ กรุณาใช้ชื่ออื่น', 'error');
    }
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold">Speaker Profiles</h2>
          <p className="text-sm text-[#9ca3af]">จัดการข้อมูลผู้พูด — ใช้ ID เป็น key รองรับชื่อซ้ำ</p>
        </div>
        <button onClick={() => setShowNew(true)} className="flex items-center gap-1.5 px-4 py-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white rounded-lg text-sm font-medium transition-colors">
          <Plus className="w-4 h-4" /> เพิ่มผู้พูด
        </button>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#e5e7eb] text-left">
            <th className="py-2 px-3 font-medium text-[#6b7280] w-8">ID</th>
            <th className="py-2 px-3 font-medium text-[#6b7280]">ชื่อเล่น</th>
            <th className="py-2 px-3 font-medium text-[#6b7280]">ชื่อ-สกุล</th>
            <th className="py-2 px-3 font-medium text-[#6b7280]">หน่วยงาน</th>
            <th className="py-2 px-3 font-medium text-[#6b7280]">แผนก</th>
            <th className="py-2 px-3 font-medium text-[#6b7280]">ตำแหน่ง</th>
            <th className="py-2 px-3 font-medium text-[#6b7280]">เสียง</th>
            <th className="py-2 px-3 w-10"></th>
          </tr>
        </thead>
        <tbody>
          {speakers.map(s => (
            <tr key={s.id} className="border-b border-[#f3f4f6] hover:bg-[#f9fafb] transition-colors">
              <td className="py-2 px-3 text-[#9ca3af] text-xs">{s.id}</td>
              <td className="py-2 px-3"><EditableCell value={s.nickname} onSave={v => handleEdit(s.id, 'nickname', v)} /></td>
              <td className="py-2 px-3"><EditableCell value={s.full_name} onSave={v => handleEdit(s.id, 'full_name', v)} /></td>
              <td className="py-2 px-3"><EditableCell value={s.organization} onSave={v => handleEdit(s.id, 'organization', v)} /></td>
              <td className="py-2 px-3"><EditableCell value={s.department} onSave={v => handleEdit(s.id, 'department', v)} /></td>
              <td className="py-2 px-3"><EditableCell value={s.position} onSave={v => handleEdit(s.id, 'position', v)} /></td>
              <td className="py-2 px-3 text-xs text-[#9ca3af]">{Math.floor(s.total_seconds / 60)}m ({s.num_sessions})</td>
              <td className="py-2 px-3">
                <button onClick={() => setDeleteTarget(s)} className="text-[#9ca3af] hover:text-[#ef4444] transition-colors">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </td>
            </tr>
          ))}
          {!speakers.length && (
            <tr><td colSpan="8" className="py-8 text-center text-[#9ca3af]">ยังไม่มีผู้พูด</td></tr>
          )}
        </tbody>
      </table>

      {deleteTarget && (
        <Modal title="ลบผู้พูด" message={`ลบ "${deleteTarget.nickname}" (ID: ${deleteTarget.id})?`} okText="ลบ" danger onConfirm={handleDelete} onCancel={() => setDeleteTarget(null)} />
      )}
      {showNew && (
        <Modal title="เพิ่มผู้พูดใหม่" type="prompt" placeholder="ชื่อเล่น" okText="เพิ่ม" onConfirm={handleCreate} onCancel={() => setShowNew(false)} />
      )}
    </div>
  );
}

function EditableCell({ value, onSave }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value || '');

  useEffect(() => { setText(value || ''); }, [value]);

  if (editing) {
    return (
      <input autoFocus value={text} onChange={e => setText(e.target.value)}
        onBlur={() => { onSave(text); setEditing(false); }}
        onKeyDown={e => { if (e.key === 'Enter') { onSave(text); setEditing(false); } if (e.key === 'Escape') { setText(value || ''); setEditing(false); } }}
        className="w-full px-2 py-1 border border-[#2563eb] rounded text-sm focus:outline-none" />
    );
  }

  return (
    <span onClick={() => setEditing(true)} className="cursor-pointer hover:bg-[#f3f4f6] px-2 py-1 rounded transition-colors block">
      {value || <span className="text-[#d1d5db]">-</span>}
    </span>
  );
}

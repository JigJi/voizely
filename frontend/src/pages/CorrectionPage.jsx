import { useState, useEffect } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import { getCorrections, addCorrection, deleteCorrection } from '../api';
import Modal from '../components/Modal';

export default function CorrectionPage() {
  const [items, setItems] = useState([]);
  const [wrong, setWrong] = useState('');
  const [correct, setCorrect] = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null);

  useEffect(() => { load(); }, []);
  async function load() { setItems(await getCorrections()); }

  async function handleAdd() {
    if (!wrong.trim() || !correct.trim()) return;
    await addCorrection(wrong.trim(), correct.trim());
    setWrong(''); setCorrect('');
    load();
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    await deleteCorrection(deleteTarget);
    setDeleteTarget(null);
    load();
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h2 className="text-lg font-semibold mb-1">Correction Dictionary</h2>
      <p className="text-sm text-[#9ca3af] mb-6">คำที่เพิ่มจะถูก auto-correct ทุกครั้งที่ถอดเสียงใหม่</p>

      <div className="flex gap-2 mb-6">
        <input value={wrong} onChange={e => setWrong(e.target.value)} placeholder="คำผิด"
          className="flex-1 px-3 py-2.5 border border-[#d1d5db] rounded-lg text-sm focus:outline-none focus:border-[#2563eb]"
          onKeyDown={e => e.key === 'Enter' && handleAdd()} />
        <input value={correct} onChange={e => setCorrect(e.target.value)} placeholder="คำถูก"
          className="flex-1 px-3 py-2.5 border border-[#d1d5db] rounded-lg text-sm focus:outline-none focus:border-[#2563eb]"
          onKeyDown={e => e.key === 'Enter' && handleAdd()} />
        <button onClick={handleAdd} className="px-4 py-2.5 bg-[#2563eb] hover:bg-[#1d4ed8] text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5">
          <Plus className="w-4 h-4" /> เพิ่ม
        </button>
      </div>

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#e5e7eb] text-left">
            <th className="py-2 px-3 font-medium text-[#6b7280]">คำผิด</th>
            <th className="py-2 px-3 font-medium text-[#6b7280]">คำถูก</th>
            <th className="py-2 px-3 w-10"></th>
          </tr>
        </thead>
        <tbody>
          {items.map(item => (
            <tr key={item.id} className="border-b border-[#f3f4f6] hover:bg-[#f9fafb] transition-colors">
              <td className="py-2 px-3">{item.wrong}</td>
              <td className="py-2 px-3">{item.correct}</td>
              <td className="py-2 px-3">
                <button onClick={() => setDeleteTarget(item.id)} className="text-[#9ca3af] hover:text-[#ef4444] transition-colors">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </td>
            </tr>
          ))}
          {!items.length && <tr><td colSpan="3" className="py-8 text-center text-[#9ca3af]">ยังไม่มีรายการ</td></tr>}
        </tbody>
      </table>

      {deleteTarget && (
        <Modal title="ลบรายการ" message="ต้องการลบรายการนี้?" okText="ลบ" danger onConfirm={handleDelete} onCancel={() => setDeleteTarget(null)} />
      )}
    </div>
  );
}

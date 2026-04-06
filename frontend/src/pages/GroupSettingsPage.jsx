import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Trash2 } from 'lucide-react';
import { updateGroup, deleteGroup } from '../api';
import Modal from '../components/Modal';

export default function GroupSettingsPage() {
  const { groupId } = useParams();
  const navigate = useNavigate();
  const [group, setGroup] = useState(null);
  const [instructions, setInstructions] = useState('');
  const [showDelete, setShowDelete] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => { loadGroup(); }, [groupId]);

  async function loadGroup() {
    const groups = await (await fetch('/api/groups')).json();
    const g = groups.find(g => g.id === parseInt(groupId));
    if (g) { setGroup(g); setInstructions(g.custom_instructions || ''); }
  }

  async function saveInstructions() {
    await updateGroup(groupId, { custom_instructions: instructions });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  async function handleDelete() {
    await deleteGroup(groupId);
    navigate('/');
  }

  if (!group) return <div className="flex items-center justify-center h-full text-[#9ca3af]">กำลังโหลด...</div>;

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h2 className="text-lg font-semibold mb-1">{group.name}</h2>
      <p className="text-sm text-[#9ca3af] mb-6">ตั้งค่ากลุ่ม</p>

      <label className="block text-sm font-medium mb-1.5">Custom Instructions</label>
      <p className="text-xs text-[#9ca3af] mb-2">คำสั่งพิเศษสำหรับ LLM ในการสรุป MoM ของกลุ่มนี้</p>
      <textarea
        value={instructions}
        onChange={e => setInstructions(e.target.value)}
        rows={4}
        className="w-full px-3 py-2.5 border border-[#d1d5db] rounded-lg text-sm focus:outline-none focus:border-[#2563eb] resize-y mb-2"
        placeholder='เช่น "สรุปเน้น action items ของฝ่ายขาย"'
      />
      <button onClick={saveInstructions} className="px-4 py-2 bg-[#2563eb] hover:bg-[#1d4ed8] text-white rounded-lg text-sm font-medium transition-colors">
        {saved ? '✓ บันทึกแล้ว' : 'บันทึก'}
      </button>

      {!group.is_default && (
        <div className="mt-12 pt-6 border-t border-[#e5e7eb]">
          <button onClick={() => setShowDelete(true)} className="flex items-center gap-2 px-4 py-2 text-sm text-[#ef4444] border border-[#fca5a5] rounded-lg hover:bg-[#fef2f2] transition-colors">
            <Trash2 className="w-4 h-4" /> ลบกลุ่มนี้
          </button>
        </div>
      )}

      {showDelete && (
        <Modal title="ลบกลุ่ม" message={`ลบ "${group.name}"? รายการทั้งหมดจะย้ายไปกลุ่ม "ทั่วไป"`} okText="ลบ" danger onConfirm={handleDelete} onCancel={() => setShowDelete(false)} />
      )}
    </div>
  );
}

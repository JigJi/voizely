import { useState, useEffect, useRef } from 'react';
import { X, Pencil, RefreshCw, Download } from 'lucide-react';
import { marked } from 'marked';
import { saveMomFull, regenerateMom, exportDocxUrl } from '../api';
import { notify } from '../components/Notification';
import Modal from '../components/Modal';

function convertMdTables(md) {
  const lines = md.split('\n');
  const result = [];
  let i = 0;
  while (i < lines.length) {
    if (lines[i].trim().startsWith('|') && i + 1 < lines.length && /^\|[\s-:|]+\|$/.test(lines[i+1].trim())) {
      const headers = lines[i].split('|').filter(c => c.trim()).map(c => c.trim());
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].trim().startsWith('|')) {
        rows.push(lines[i].split('|').filter(c => c.trim()).map(c => c.trim()));
        i++;
      }
      let html = '<table class="mom-table"><thead><tr>';
      headers.forEach(h => html += '<th>' + h + '</th>');
      html += '</tr></thead><tbody>';
      rows.forEach(row => { html += '<tr>'; row.forEach(c => html += '<td>' + c + '</td>'); html += '</tr>'; });
      html += '</tbody></table>';
      result.push(html);
    } else {
      result.push(lines[i]);
      i++;
    }
  }
  return result.join('\n');
}

export default function MomModal({ transcription, onClose, onUpdate }) {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(transcription.mom_full || transcription.summary || '');
  const [showRegen, setShowRegen] = useState(false);
  const [saving, setSaving] = useState(false);
  const viewRef = useRef();

  useEffect(() => {
    if (viewRef.current && !editing) {
      marked.setOptions({ gfm: true, breaks: true });
      const text = convertMdTables(content);
      viewRef.current.innerHTML = marked.parse(text);
    }
  }, [content, editing]);

  async function handleSave() {
    setSaving(true);
    await saveMomFull(transcription.id, content);
    notify('บันทึกแล้ว');
    setSaving(false);
    setEditing(false);
    onUpdate?.();
  }

  async function handleRegenerate() {
    setShowRegen(false);
    notify('กำลังสร้าง MoM ใหม่...', 'info');
    await regenerateMom(transcription.id);
    onUpdate?.();
    notify('สร้าง MoM ใหม่แล้ว');
    // Reload content
    const res = await fetch(`/api/transcriptions/${transcription.id}`);
    const data = await res.json();
    setContent(data.mom_full || data.summary || '');
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-white rounded-xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-xl" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#e5e7eb]">
          <h2 className="text-base font-semibold">Minutes of Meeting</h2>
          <div className="flex items-center gap-2">
            <button onClick={() => setEditing(!editing)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-[#d1d5db] rounded-lg hover:bg-[#f3f4f6] transition-colors">
              <Pencil className="w-3.5 h-3.5" /> {editing ? 'ดู' : 'Edit'}
            </button>
            <a href={exportDocxUrl(transcription.id)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[#2563eb] text-white rounded-lg hover:bg-[#1d4ed8] transition-colors">
              <Download className="w-3.5 h-3.5" /> Export
            </a>
            <button onClick={() => setShowRegen(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-[#d1d5db] rounded-lg hover:bg-[#f3f4f6] transition-colors">
              <RefreshCw className="w-3.5 h-3.5" /> Regenerate
            </button>
            <button onClick={onClose} className="p-1.5 hover:bg-[#f3f4f6] rounded-lg transition-colors">
              <X className="w-4 h-4 text-[#9ca3af]" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto p-6">
          {editing ? (
            <textarea
              value={content}
              onChange={e => setContent(e.target.value)}
              className="w-full h-full min-h-[400px] p-4 border border-[#d1d5db] rounded-lg text-sm font-mono focus:outline-none focus:border-[#2563eb] resize-y"
            />
          ) : (
            <div ref={viewRef} className="prose prose-sm max-w-none mom-content" />
          )}
        </div>

        {/* Footer (edit mode) */}
        {editing && (
          <div className="flex justify-end gap-2 px-6 py-3 border-t border-[#e5e7eb]">
            <button onClick={() => setEditing(false)} className="px-4 py-2 text-sm border border-[#d1d5db] rounded-lg hover:bg-[#f3f4f6]">ยกเลิก</button>
            <button onClick={handleSave} disabled={saving} className="px-4 py-2 text-sm font-medium bg-[#2563eb] text-white rounded-lg hover:bg-[#1d4ed8] disabled:opacity-50">
              {saving ? 'กำลังบันทึก...' : 'บันทึก'}
            </button>
          </div>
        )}
      </div>

      {showRegen && (
        <Modal title="สร้าง MoM ใหม่?" message="ระบบจะสร้าง MoM ใหม่จาก transcript ปัจจุบัน" okText="สร้างใหม่" onConfirm={handleRegenerate} onCancel={() => setShowRegen(false)} />
      )}
    </div>
  );
}

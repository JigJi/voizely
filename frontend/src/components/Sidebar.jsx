import { useState, useEffect, useRef } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import { Upload, Plus, ChevronDown, Settings, Check, X, Loader2, Users, BookOpen, Trash2 } from 'lucide-react';
import { deleteTranscription } from '../api';
import { getGroups, getTranscriptions, createGroup } from '../api';
import Modal from './Modal';

export default function Sidebar() {
  const [groups, setGroups] = useState([]);
  const [transcriptions, setTranscriptions] = useState([]);
  const [collapsed, setCollapsed] = useState(() => JSON.parse(localStorage.getItem('collapsed_groups') || '{}'));
  const [showNewGroup, setShowNewGroup] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const { id } = useParams();
  const navigate = useNavigate();
  const fileRef = useRef();

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  async function loadData() {
    try {
      const [g, t] = await Promise.all([getGroups(), getTranscriptions()]);
      setGroups(g);
      setTranscriptions(t);
    } catch (e) { console.error(e); }
  }

  function toggleGroup(groupId) {
    const next = { ...collapsed, [groupId]: !collapsed[groupId] };
    setCollapsed(next);
    localStorage.setItem('collapsed_groups', JSON.stringify(next));
  }

  async function handleCreateGroup(name) {
    if (!name) return;
    await createGroup(name);
    loadData();
    setShowNewGroup(false);
  }

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await fetch('/htmx/upload', { method: 'POST', body: form });
      const redirect = res.headers.get('HX-Redirect');
      if (redirect) navigate(redirect);
      else {
        const text = await res.text();
        if (text.includes('HX-Redirect')) {
          const match = text.match(/HX-Redirect.*?["']([^"']+)/);
          if (match) navigate(match[1]);
        }
      }
    } catch (err) { console.error(err); }
    e.target.value = '';
  }

  // Group transcriptions
  const grouped = groups.map(g => ({
    ...g,
    items: transcriptions.filter(t =>
      g.is_default ? (!t.group_id || t.group_id === g.id) : t.group_id === g.id
    ),
  }));

  // Move default to end
  const sorted = [
    ...grouped.filter(g => !g.is_default),
    ...grouped.filter(g => g.is_default),
  ];

  return (
    <aside className="w-80 bg-[#f9fafb] border-r border-[#e5e7eb] flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-[#e5e7eb]">
        <div className="flex items-center gap-2 mb-3">
          <img src="/logo.png" alt="Voizely" className="h-6" />
        </div>
        {/* New Transcription */}
        <button onClick={() => navigate('/upload')} className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-[#2563eb] hover:bg-[#1d4ed8] text-white rounded-lg text-sm font-medium transition-all shadow-sm hover:shadow-md">
          <Plus className="w-4 h-4" />
          <span>ถอดเสียงใหม่</span>
        </button>
      </div>

      {/* Groups + Files */}
      <div className="flex-1 overflow-y-auto p-2">
        <button
          onClick={() => setShowNewGroup(true)}
          className="flex items-center gap-1.5 w-full px-3 py-2 text-sm text-[#6b7280] hover:text-[#2563eb] hover:bg-[#eff6ff] rounded transition-all"
        >
          <Plus className="w-3 h-3" /> สร้างกลุ่ม
        </button>

        {sorted.map(g => (
          <div key={g.id} className="mt-1">
            <div
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-[#6b7280] cursor-pointer hover:text-[#374151] rounded group"
              onClick={() => toggleGroup(g.id)}
            >
              <ChevronDown className={`w-3 h-3 transition-transform ${collapsed[g.id] ? '-rotate-90' : ''}`} />
              <span className="flex-1 truncate">{g.name}</span>
              <span className="text-xs text-[#9ca3af]">{g.items.length}</span>
              {!g.is_default && (
                <Link to={`/groups/${g.id}`} onClick={e => e.stopPropagation()} className="opacity-0 group-hover:opacity-100 transition-opacity">
                  <Settings className="w-3 h-3 text-[#9ca3af] hover:text-[#2563eb]" />
                </Link>
              )}
            </div>
            {!collapsed[g.id] && g.items.map(t => (
              <Link
                key={t.id}
                to={`/transcriptions/${t.id}`}
                className={`flex items-center gap-2.5 px-4 py-2 mx-1 rounded-md text-sm transition-all group ${
                  String(t.id) === id ? 'bg-[#eff6ff] text-[#2563eb]' : 'text-[#374151] hover:bg-[#f3f4f6]'
                }`}
              >
                {t.status === 'completed' ? (
                  <Check className="w-3.5 h-3.5 text-[#22c55e] shrink-0" />
                ) : t.status === 'failed' ? (
                  <X className="w-3.5 h-3.5 text-[#ef4444] shrink-0" />
                ) : (
                  <Loader2 className="w-3.5 h-3.5 text-[#2563eb] animate-spin shrink-0" />
                )}
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm">{t.auto_title || t.original_filename}</div>
                  <div className="text-xs text-[#9ca3af]">{new Date(t.created_at).toLocaleDateString('th-TH', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</div>
                </div>
                <button onClick={e => { e.preventDefault(); e.stopPropagation(); setDeleteTarget(t); }}
                  className="opacity-0 group-hover:opacity-100 p-1 text-[#9ca3af] hover:text-[#ef4444] transition-all shrink-0">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </Link>
            ))}
          </div>
        ))}
      </div>

      {/* Bottom nav */}
      <div className="border-t border-[#e5e7eb] p-2">
        <Link to="/speakers" className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-[#6b7280] hover:text-[#374151] hover:bg-[#f3f4f6] rounded-md transition-all">
          <Users className="w-4 h-4" /> Speaker
        </Link>
        <Link to="/corrections" className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-[#6b7280] hover:text-[#374151] hover:bg-[#f3f4f6] rounded-md transition-all">
          <BookOpen className="w-4 h-4" /> Correction
        </Link>
      </div>

      {deleteTarget && (
        <Modal
          title="ลบไฟล์"
          message={`ลบ "${deleteTarget.auto_title || deleteTarget.original_filename}"?`}
          okText="ลบ"
          danger
          onConfirm={async () => {
            await deleteTranscription(deleteTarget.id);
            setDeleteTarget(null);
            loadData();
            navigate('/transcriptions');
          }}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      {showNewGroup && (
        <Modal
          title="สร้างกลุ่มใหม่"
          type="prompt"
          placeholder="ชื่อกลุ่ม"
          okText="สร้าง"
          onConfirm={handleCreateGroup}
          onCancel={() => setShowNewGroup(false)}
        />
      )}
    </aside>
  );
}

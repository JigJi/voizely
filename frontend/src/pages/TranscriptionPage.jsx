import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { getTranscription, getProgress, renameSpeaker, replaceText, applyCorrections, assignGroup, updateTitle, getGroups, audioStreamUrl, getSpeakers, createSpeaker } from '../api';
import { notify } from '../components/Notification';
import ProgressSteps from '../components/ProgressSteps';
import MomModal from '../tabs/MomModal';
import Modal from '../components/Modal';
import { Pencil } from 'lucide-react';

const SPEAKER_COLORS = ['#2563eb', '#ec4899', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ef4444', '#14b8a6'];

export default function TranscriptionPage() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [tab, setTab] = useState('timeline');
  const [loading, setLoading] = useState(true);
  const [showMom, setShowMom] = useState(false);
  const [showFindReplace, setShowFindReplace] = useState(false);
  const [groups, setGroups] = useState([]);
  const [renameTarget, setRenameTarget] = useState(null);
  const [suggestedName, setSuggestedName] = useState('');
  const [suggestEdit, setSuggestEdit] = useState(null);
  const audioRef = useRef();

  useEffect(() => { loadData(); getGroups().then(setGroups); }, [id]);

  useEffect(() => {
    if (!data || data.status === 'completed') return;
    const interval = setInterval(async () => {
      const p = await getProgress(id);
      if (p.status !== data.status) loadData();
      else setData(prev => prev ? { ...prev, ...p } : prev);
    }, 2000);
    return () => clearInterval(interval);
  }, [data?.status, id]);

  async function loadData() {
    setLoading(true);
    try { setData(await getTranscription(id)); } catch (e) { console.error(e); }
    setLoading(false);
  }

  if (loading) return <div className="flex items-center justify-center h-full text-[#9ca3af]">กำลังโหลด...</div>;
  if (!data) return <div className="flex items-center justify-center h-full text-[#ef4444]">ไม่พบข้อมูล</div>;
  if (data.status === 'pending' || data.status === 'in_progress') return <ProgressSteps progress={data.progress_percent || 0} statusMessage={data.status_message || ''} />;
  if (data.status === 'failed') return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <div className="text-[#ef4444] text-lg font-medium mb-2">เกิดข้อผิดพลาด</div>
        <div className="text-sm text-[#6b7280]">{data.status_message}</div>
      </div>
    </div>
  );

  const speakerColorMap = {};
  let colorIdx = 0;
  (data.segments || []).forEach(s => {
    if (s.speaker && !speakerColorMap[s.speaker]) {
      speakerColorMap[s.speaker] = SPEAKER_COLORS[colorIdx % SPEAKER_COLORS.length];
      colorIdx++;
    }
  });

  const tabs = [
    { key: 'timeline', label: 'Timeline' },
    { key: 'summary', label: 'Summary' },
  ];

  return (
    <div className="h-full flex flex-col">
      {/* Audio player */}
      <div className="px-6 py-3 border-b border-[#e5e7eb] bg-[#fafafa]">
        <audio ref={audioRef} controls className="w-full h-8" src={audioStreamUrl(data.audio_file_id)} />
        <div className="flex items-center gap-2 mt-1 text-xs text-[#9ca3af]">
          <EditableText value={data.original_filename} onSave={v => {}} />
          <span>·</span>
          <span>{data.detected_language || '?'}</span>
          <span>·</span>
          <span>{Math.round(data.processing_time_seconds || 0)}s</span>
        </div>
      </div>

      {/* Tabs + actions */}
      <div className="flex items-center border-b border-[#e5e7eb] px-6">
        {tabs.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${tab === t.key ? 'text-[#2563eb] border-[#2563eb]' : 'text-[#9ca3af] border-transparent hover:text-[#374151]'}`}>
            {t.label}
          </button>
        ))}
        <div className="flex-1" />
        <div className="flex gap-2">
          <button onClick={() => setShowFindReplace(!showFindReplace)} className="px-3 py-1.5 text-xs border border-[#d1d5db] rounded-md hover:bg-[#f3f4f6] transition-colors">ค้นหา/แก้คำ</button>
          <button onClick={async () => { const r = await applyCorrections(id); notify(`แก้ไข ${r.count} จุด`); if (r.count > 0) loadData(); }}
            className="px-3 py-1.5 text-xs border border-[#d1d5db] rounded-md hover:bg-[#f3f4f6] transition-colors">Correction</button>
          <button onClick={() => setShowMom(true)} className="px-3 py-1.5 text-xs bg-[#2563eb] text-white rounded-md hover:bg-[#1d4ed8] transition-colors">MoM</button>
        </div>
      </div>

      {/* Find & Replace bar */}
      {showFindReplace && <FindReplaceBar transcriptionId={id} onDone={() => { setShowFindReplace(false); loadData(); }} />}

      {/* Content */}
      <div className="flex-1 overflow-auto flex">
        <div className="flex-1 p-6 overflow-auto">
          {tab === 'summary' && <SummaryContent data={data} onTitleSave={async (v) => { await updateTitle(id, v); loadData(); }} />}
          {tab === 'timeline' && <TimelineContent data={data} colorMap={speakerColorMap} audioRef={audioRef} />}
        </div>

        {/* Right panel */}
        <div className="w-72 border-l border-[#e5e7eb] p-5 shrink-0 hidden lg:flex flex-col">
          {/* Group */}
          <div className="mb-5">
            <div className="text-sm font-medium text-[#6b7280] mb-1.5">กลุ่ม</div>
            <select value={data.group_id || ''} onChange={async (e) => { await assignGroup(id, parseInt(e.target.value)); notify('ย้ายกลุ่มแล้ว'); loadData(); }}
              className="w-full px-3 py-2 text-sm border border-[#e5e7eb] rounded-lg focus:outline-none focus:border-[#2563eb]">
              {groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          </div>

          {/* Quality */}
          {data.deepgram_confidence > 0 && (
            <div className="mb-5 flex items-center justify-between">
              <div className="text-sm font-medium text-[#6b7280]">คุณภาพเสียง</div>
              <div className={`text-sm font-semibold ${data.deepgram_confidence >= 0.8 ? 'text-[#22c55e]' : 'text-[#f59e0b]'}`}>
                {Math.round(data.deepgram_confidence * 100)}%
              </div>
            </div>
          )}

          {/* Speakers */}
          {Object.keys(speakerColorMap).length > 0 && (
            <div className="mb-5">
              <div className="text-base font-medium text-[#6b7280] mb-2">ผู้พูด</div>
              <div className="grid gap-y-1.5" style={{ gridTemplateColumns: 'auto 1fr auto' }}>
                {(() => {
                  const llmSuggestions = data.speaker_suggestions ? JSON.parse(data.speaker_suggestions) : [];
                  const vpSuggestions = data.voiceprint_suggestions ? JSON.parse(data.voiceprint_suggestions) : [];
                  const totalAll = (data.segments || []).reduce((sum, s) => sum + (s.end_time - s.start_time), 0);
                  const items = Object.entries(speakerColorMap).map(([name, color]) => {
                    const totalSec = (data.segments || []).filter(s => s.speaker === name).reduce((sum, s) => sum + (s.end_time - s.start_time), 0);
                    const pct = totalAll > 0 ? Math.round(totalSec / totalAll * 100) : 0;
                    // Get suggestions
                    const llm = name.startsWith('Speaker ') ? llmSuggestions.find(s => s.speaker === name) : null;
                    const vp = name.startsWith('Speaker ') ? vpSuggestions.find(s => s.speaker === name) : null;
                    // Decide which to show
                    let suggest = null;
                    if (llm && vp && llm.suggested_name === vp.suggested_name) {
                      suggest = { name: llm.suggested_name, color: '#22c55e', source: 'both' }; // green = both agree
                    } else if (llm && vp) {
                      // Pick higher confidence: vp has score, llm doesn't — prefer vp if score >= 0.7
                      suggest = vp.score >= 0.70
                        ? { name: vp.suggested_name, color: '#f59e0b', source: 'voiceprint' } // orange
                        : { name: llm.suggested_name, color: '#2563eb', source: 'llm' }; // blue
                    } else if (llm) {
                      suggest = { name: llm.suggested_name, color: '#2563eb', source: 'llm' };
                    } else if (vp) {
                      suggest = { name: vp.suggested_name, color: '#f59e0b', source: 'voiceprint' };
                    }
                    return { name, color, pct, suggest };
                  }).sort((a, b) => b.pct - a.pct);

                  const hasSuggestions = items.some(i => i.suggest);
                  return (<>
                  {items.map(({ name, color, pct, suggest }) => (
                    <React.Fragment key={name}>
                      <div className="flex items-center gap-1 pr-2 whitespace-nowrap">
                        <SpeakerDropdown name={name} onSelect={async (newName) => {
                          if (newName && newName !== name) { await renameSpeaker(id, name, newName); notify(`เปลี่ยน ${name} → ${newName}`); loadData(); }
                        }} />
                        {suggest && (
                          <span className="px-1.5 py-0.5 rounded text-[10px]"
                            style={{ background: suggest.color + '18', color: suggest.color }}
                            title={suggest.source === 'both' ? 'AI + Voiceprint ตรงกัน' : suggest.source === 'voiceprint' ? 'จาก Voiceprint' : 'จาก AI'}>
                            {suggest.name}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center">
                        <div className="w-full h-1.5 bg-[#f3f4f6] rounded-full overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
                        </div>
                      </div>
                      <span className="text-[#9ca3af] text-sm text-right pl-1">{pct}%</span>
                    </React.Fragment>
                  ))}
                  {hasSuggestions && (
                    <div className="col-span-3 flex gap-3 mt-2 pt-2 border-t border-[#f3f4f6]">
                      <span className="flex items-center gap-1 text-[9px] text-[#9ca3af]"><span className="w-2 h-2 rounded-full bg-[#22c55e]" />AI+Voice ตรงกัน</span>
                      <span className="flex items-center gap-1 text-[9px] text-[#9ca3af]"><span className="w-2 h-2 rounded-full bg-[#2563eb]" />AI แนะนำ</span>
                      <span className="flex items-center gap-1 text-[9px] text-[#9ca3af]"><span className="w-2 h-2 rounded-full bg-[#f59e0b]" />Voiceprint</span>
                    </div>
                  )}
                  </>);
                })()}
              </div>
            </div>
          )}

          {/* Spacer */}
          <div className="flex-1" />

          {/* Cost (bottom) */}
          {data.total_cost_usd > 0 && (
            <div className="pt-4 border-t border-[#e5e7eb]">
              <div className="text-xs font-medium text-[#9ca3af] mb-1">ค่าใช้จ่าย</div>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between"><span className="text-[#9ca3af]">{{'deepgram': 'Deepgram', 'spectral': 'Deepgram + Spectral', 'pyannote': 'Pyannote', 'gemini': 'Gemini'}[data.model_size?.split('+')[0]] || data.model_size?.split('+')[0]}</span><span>{((data.deepgram_cost_usd || 0) * 34.5).toFixed(2)} บาท</span></div>
                <div className="flex justify-between"><span className="text-[#9ca3af]">Gemini</span><span>{((data.gemini_cost_usd || 0) * 34.5).toFixed(2)} บาท</span></div>
                <div className="flex justify-between font-medium border-t border-[#e5e7eb] pt-1 mt-1"><span>รวม</span><span>{((data.total_cost_usd || 0) * 34.5).toFixed(2)} บาท</span></div>
              </div>
            </div>
          )}
        </div>
      </div>

      {showMom && <MomModal transcription={data} onClose={() => setShowMom(false)} onUpdate={loadData} />}
      {renameTarget && (
        <Modal title="เปลี่ยนชื่อผู้พูด" type="prompt" value={suggestedName || renameTarget} placeholder="ชื่อใหม่" okText="เปลี่ยน"
          onConfirm={async (v) => { if (v && v !== renameTarget) { await renameSpeaker(id, renameTarget, v); notify('เปลี่ยนชื่อแล้ว'); loadData(); } setRenameTarget(null); setSuggestedName(''); }}
          onCancel={() => { setRenameTarget(null); setSuggestedName(''); }} />
      )}
    </div>
  );
}

function EditableText({ value, onSave }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value || '');
  if (editing) return (
    <input autoFocus value={text} onChange={e => setText(e.target.value)}
      onBlur={() => { onSave(text); setEditing(false); }}
      onKeyDown={e => { if (e.key === 'Enter') { onSave(text); setEditing(false); } if (e.key === 'Escape') setEditing(false); }}
      className="px-1 py-0.5 border border-[#2563eb] rounded text-xs focus:outline-none" />
  );
  return <span onClick={() => setEditing(true)} className="cursor-pointer hover:text-[#2563eb] transition-colors">{value}</span>;
}

function FindReplaceBar({ transcriptionId, onDone }) {
  const [find, setFind] = useState('');
  const [replace, setReplace] = useState('');
  async function handleReplace() {
    if (!find) return;
    const r = await replaceText(transcriptionId, find, replace);
    notify(`แก้ไข ${r.count} จุด`);
    if (r.count > 0) onDone();
  }
  return (
    <div className="flex items-center gap-2 px-6 py-2 bg-[#f9fafb] border-b border-[#e5e7eb]">
      <input value={find} onChange={e => setFind(e.target.value)} placeholder="ค้นหา..." className="flex-1 px-3 py-1.5 text-sm border border-[#d1d5db] rounded-md focus:outline-none focus:border-[#2563eb]" onKeyDown={e => e.key === 'Enter' && handleReplace()} />
      <span className="text-[#9ca3af]">→</span>
      <input value={replace} onChange={e => setReplace(e.target.value)} placeholder="แก้เป็น..." className="flex-1 px-3 py-1.5 text-sm border border-[#d1d5db] rounded-md focus:outline-none focus:border-[#2563eb]" onKeyDown={e => e.key === 'Enter' && handleReplace()} />
      <button onClick={handleReplace} className="px-3 py-1.5 text-sm bg-[#2563eb] text-white rounded-md hover:bg-[#1d4ed8]">แก้ทั้งหมด</button>
      <button onClick={onDone} className="px-3 py-1.5 text-sm border border-[#d1d5db] rounded-md hover:bg-[#f3f4f6]">ปิด</button>
    </div>
  );
}

function SummaryContent({ data, onTitleSave }) {
  const topics = data.topics ? JSON.parse(data.topics) : [];
  const decisions = data.key_decisions ? JSON.parse(data.key_decisions) : [];
  const actions = data.action_items ? JSON.parse(data.action_items) : [];

  return (
    <div className="w-full">
      <EditableText value={data.auto_title || data.original_filename} onSave={onTitleSave} />
      {data.summary_short && <p className="text-sm text-[#6b7280] mt-1 mb-4">{data.summary_short}</p>}

      <div className="flex gap-2 mb-4 flex-wrap items-center">
        {data.meeting_type && (
          <span className="px-2.5 py-1 bg-[#f3f4f6] rounded-full text-xs">
            <span className="text-[#9ca3af]">ประเภท:</span> {data.meeting_type}
          </span>
        )}
        {data.sentiment && (
          <span className="px-2.5 py-1 bg-[#f3f4f6] rounded-full text-xs">
            <span className="text-[#9ca3af]">บรรยากาศ:</span> {data.sentiment}
          </span>
        )}
      </div>

      {topics.length > 0 && (
        <div className="mb-6">
          <div className="text-xs text-[#9ca3af] mb-1.5">หัวข้อที่พูดถึง</div>
          <div className="flex gap-2 flex-wrap">
            {topics.map((t, i) => <span key={i} className="px-2.5 py-1 bg-[#eff6ff] text-[#1e40af] rounded-full text-xs">{t}</span>)}
          </div>
        </div>
      )}

      {decisions.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-medium mb-2">มติ/ข้อสรุป</h3>
          <ul className="space-y-1">
            {decisions.map((d, i) => <li key={i} className="text-sm text-[#4b5563] pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-[#9ca3af]">{d}</li>)}
          </ul>
        </div>
      )}

      {actions.length > 0 && (
        <div>
          <h3 className="text-sm font-medium mb-2">สิ่งที่ต้องทำ</h3>
          <ul className="space-y-1">
            {actions.map((a, i) => <li key={i} className="text-sm text-[#4b5563] pl-4 relative before:content-['•'] before:absolute before:left-0 before:text-[#9ca3af]">{a.task}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function TimelineContent({ data, colorMap, audioRef }) {
  const [activeIdx, setActiveIdx] = useState(-1);

  useEffect(() => {
    if (!audioRef?.current) return;
    const audio = audioRef.current;
    function onTimeUpdate() {
      const t = audio.currentTime;
      const idx = (data.segments || []).findIndex(s => t >= s.start_time - 0.2 && t < s.end_time + 0.5);
      setActiveIdx(idx);
    }
    audio.addEventListener('timeupdate', onTimeUpdate);
    return () => audio.removeEventListener('timeupdate', onTimeUpdate);
  }, [audioRef, data.segments]);

  if (!data.segments?.length) return <div className="text-[#9ca3af] text-sm">ไม่มีข้อมูล</div>;

  return (
    <div>
      {/* Segments */}
      <div className="space-y-0.5">
        {data.segments.map((seg, i) => (
          <div key={i} className={`flex gap-3 py-2 rounded-md px-2 transition-colors cursor-pointer group ${i === activeIdx ? 'bg-[#eff6ff] border-l-2 border-[#2563eb]' : 'hover:bg-[#f9fafb]'}`}
            onClick={() => { if (audioRef?.current) { audioRef.current.currentTime = seg.start_time; audioRef.current.play(); } }}>
            <div className="text-sm text-[#9ca3af] w-16 shrink-0 pt-0.5 font-mono">
              {Math.floor(seg.start_time / 60)}:{String(Math.floor(seg.start_time % 60)).padStart(2, '0')}
            </div>
            <div className="w-1 shrink-0 rounded-full" style={{ background: colorMap[seg.speaker] || '#e5e7eb' }} />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium mb-0.5" style={{ color: colorMap[seg.speaker] || '#6b7280' }}>{seg.speaker}</div>
              <div className="text-[15px] text-[#374151] leading-relaxed">{seg.text}</div>
            </div>
          </div>
        ))}
      </div>

    </div>
  );
}

function InlineSuggestEdit({ value, onSave, onCancel }) {
  const [text, setText] = useState(value);
  return (
    <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
      <input autoFocus value={text} onChange={e => setText(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') onSave(text.trim()); if (e.key === 'Escape') onCancel(); }}
        className="w-20 px-1.5 py-0.5 text-xs border border-[#2563eb] rounded focus:outline-none" />
      <button onClick={() => onSave(text.trim())} className="px-1.5 py-0.5 bg-[#2563eb] text-white rounded text-[10px] hover:bg-[#1d4ed8]">✓</button>
      <button onClick={onCancel} className="px-1 py-0.5 text-[#9ca3af] text-[10px] hover:text-[#ef4444]">✕</button>
    </div>
  );
}

function SpeakerDropdown({ name, onSelect }) {
  const [open, setOpen] = useState(false);
  const [speakers, setSpeakers] = useState([]);
  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState('');
  const [search, setSearch] = useState('');
  const dropRef = useRef();

  useEffect(() => {
    if (open) {
      getSpeakers().then(setSpeakers);
    }
  }, [open]);

  useEffect(() => {
    function handleClick(e) {
      if (dropRef.current && !dropRef.current.contains(e.target)) { setOpen(false); setSearch(''); }
    }
    if (open) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const [newError, setNewError] = useState('');

  async function handleNewSpeaker() {
    if (!newName.trim()) return;
    try {
      await createSpeaker({ nickname: newName.trim() });
      onSelect(newName.trim());
      setOpen(false);
      setShowNew(false);
      setNewName('');
      setNewError('');
    } catch (e) {
      setNewError('ชื่อนี้มีอยู่แล้ว');
    }
  }

  return (
    <div className="relative" ref={dropRef}>
      <span className="cursor-pointer hover:text-[#2563eb] transition-colors text-sm"
        onClick={() => setOpen(!open)}>
        {name}
      </span>
      {open && (
        <div className="absolute top-6 left-0 z-50 bg-white border border-[#e5e7eb] rounded-lg shadow-lg w-[200px] py-1">
          {/* Search */}
          <div className="px-2 py-1">
            <input autoFocus value={search} onChange={e => setSearch(e.target.value)}
              placeholder="ค้นหา..."
              className="w-full px-2 py-1 text-sm border border-[#e5e7eb] rounded focus:outline-none focus:border-[#2563eb]" />
          </div>
          {/* List */}
          <div className="max-h-[200px] overflow-y-auto">
            {(() => {
              const nickCount = {};
              speakers.forEach(s => { nickCount[s.nickname] = (nickCount[s.nickname] || 0) + 1; });
              const filtered = speakers.filter(s => !search || s.nickname.toLowerCase().includes(search.toLowerCase()) || (s.full_name || '').toLowerCase().includes(search.toLowerCase()));
              return filtered.map(s => {
                const isDup = nickCount[s.nickname] > 1;
                const hint = isDup ? (s.department || s.full_name || `#${s.id}`) : (s.full_name || '');
                return (
                  <button key={s.id} onClick={() => { onSelect(s.nickname); setOpen(false); setSearch(''); }}
                    className="w-full text-left px-3 py-1.5 text-sm hover:bg-[#f3f4f6] transition-colors flex items-center justify-between">
                    <span className="truncate">{s.nickname}</span>
                    {hint && <span className="text-[10px] text-[#9ca3af] ml-1 truncate max-w-[60px]">{hint}</span>}
                  </button>
                );
              });
            })()}
          </div>
          <div className="border-t border-[#e5e7eb] my-1" />
          {!showNew ? (
            <button onClick={() => setShowNew(true)}
              className="w-full text-left px-3 py-1.5 text-sm text-[#2563eb] hover:bg-[#eff6ff] transition-colors">
              + เพิ่มผู้พูดใหม่
            </button>
          ) : (
            <div className="px-2 py-1.5">
              <div className="flex gap-1">
                <input autoFocus value={newName} onChange={e => { setNewName(e.target.value); setNewError(''); }}
                  onKeyDown={e => { if (e.key === 'Enter') handleNewSpeaker(); if (e.key === 'Escape') { setShowNew(false); setNewName(''); setNewError(''); } }}
                  placeholder="ชื่อเรียก"
                  className={`min-w-0 flex-1 px-2 py-1 text-xs border rounded focus:outline-none ${newError ? 'border-[#ef4444]' : 'border-[#d1d5db] focus:border-[#2563eb]'}`} />
                <button onClick={handleNewSpeaker} className="px-1.5 py-1 text-[10px] bg-[#2563eb] text-white rounded hover:bg-[#1d4ed8] shrink-0">ตกลง</button>
              </div>
              {newError && <div className="text-[10px] text-[#ef4444] mt-1">{newError}</div>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}



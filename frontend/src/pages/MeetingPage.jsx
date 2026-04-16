import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, RefreshCw, RotateCcw, CheckCircle, XCircle, Clock, Download, Loader2, Users } from 'lucide-react';
import { getMeetings, processMeeting, retranscribeMeeting, retryMeeting, getGroups, downloadMeetingAudio } from '../api';
import { notify } from '../components/Notification';

const STATUS_MAP = {
  discovered: { label: 'New', color: '#3b82f6', icon: Download },
  downloading: { label: 'Downloading', color: '#f59e0b', icon: Loader2 },
  queued: { label: 'Processing', color: '#8b5cf6', icon: Loader2 },
  completed: { label: 'Success', color: '#22c55e', icon: CheckCircle },
  failed: { label: 'Failed', color: '#ef4444', icon: XCircle },
};

function formatDate(isoStr) {
  if (!isoStr) return '-';
  const d = new Date(isoStr);
  return d.toLocaleDateString('th-TH', { day: 'numeric', month: 'short', year: '2-digit' }) +
    ' ' + d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' });
}

export default function MeetingPage() {
  const [meetings, setMeetings] = useState([]);
  const [groups, setGroups] = useState([]);
  const [processTarget, setProcessTarget] = useState(null);
  const [processMode, setProcessMode] = useState('process');
  const [selectedGroup, setSelectedGroup] = useState('');
  const [selectedDiarization, setSelectedDiarization] = useState('smart');
  const [selectedTranscription, setSelectedTranscription] = useState('gemini');
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    try {
      const [m, g] = await Promise.all([getMeetings(), getGroups()]);
      setMeetings(m);
      setGroups(g);
    } catch (e) { notify('โหลดข้อมูลไม่ได้', 'error'); }
    setLoading(false);
  }

  async function handleProcess() {
    if (!processTarget) return;
    try {
      const modelSize = `${selectedDiarization}+${selectedTranscription}`;
      const apiCall = processMode === 'retranscribe' ? retranscribeMeeting : processMeeting;
      const res = await apiCall(processTarget.id, selectedGroup || null, modelSize);
      setProcessTarget(null);
      setSelectedGroup('');
      setSelectedDiarization('smart');
      setSelectedTranscription('gemini');
      if (res.transcription_id) {
        notify(processMode === 'retranscribe' ? 'เริ่มถอดเสียงใหม่แล้ว' : 'เริ่มถอดเสียงแล้ว');
        navigate(`/transcriptions/${res.transcription_id}`);
      } else {
        notify('กำลังดาวน์โหลดไฟล์... รอสักครู่แล้วกดรีเฟรช');
        load();
      }
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'เกิดข้อผิดพลาด';
      notify(msg, 'error');
    }
  }

  function openProcessModal(m, mode) {
    setProcessTarget(m);
    setProcessMode(mode);
    setSelectedGroup('');
    setSelectedDiarization('smart');
    setSelectedTranscription('gemini');
  }

  async function handleRetry(id) {
    try {
      await retryMeeting(id);
      notify('กำลังลองใหม่');
      load();
    } catch (e) { notify(e.message, 'error'); }
  }

  async function handleDownload(m) {
    try {
      notify('กำลังดาวน์โหลด...');
      await downloadMeetingAudio(m.id, m.meeting_subject);
    } catch (e) {
      notify(e.message || 'ดาวน์โหลดไม่สำเร็จ', 'error');
    }
  }

  const platformIcon = (p) => p === 'teams' ? '🟦' : p === 'zoom' ? '🟪' : '🟩';

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold">Meeting Recordings</h2>
          <p className="text-sm text-[#9ca3af]">รายการบันทึกการประชุมจาก Teams / Zoom / Meet</p>
        </div>
        <button onClick={load} className="flex items-center gap-1.5 px-3 py-2 text-sm text-[#6b7280] hover:text-[#374151] hover:bg-[#f3f4f6] rounded-lg transition-colors">
          <RefreshCw className="w-4 h-4" /> รีเฟรช
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-16 text-[#9ca3af]">
          <Loader2 className="w-5 h-5 animate-spin mr-2" /> กำลังโหลด...
        </div>
      ) : !meetings.length ? (
        <div className="text-center py-16 text-[#9ca3af]">
          <p className="text-lg mb-2">ยังไม่มีรายการบันทึกการประชุม</p>
          <p className="text-sm">ระบบจะดึงมาอัตโนมัติเมื่อมีการอัดเสียงใน Teams</p>
        </div>
      ) : (
        <div className="space-y-3">
          {meetings.map(m => {
            const st = STATUS_MAP[m.status] || STATUS_MAP.discovered;
            const Icon = st.icon;
            return (
              <div key={m.id} className="border border-[#e5e7eb] rounded-lg p-4 hover:border-[#d1d5db] transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-base">{platformIcon(m.platform)}</span>
                      <h3 className="font-medium text-sm truncate">{m.meeting_subject || m.file_name || 'ไม่มีชื่อ'}</h3>
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium shrink-0" style={{ color: st.color, backgroundColor: st.color + '15' }}>
                        <Icon className="w-3 h-3" /> {st.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-[#9ca3af]">
                      <span>{m.meeting_organizer}</span>
                      <span>{formatDate(m.meeting_start_time || m.discovered_at)}</span>
                      {m.file_size_mb && <span>{m.file_size_mb} MB</span>}
                      {m.processed_by_name && (
                        <span className="text-[#6b7280]">ถอดโดย {m.processed_by_name}</span>
                      )}
                      {m.transcription_status && m.transcription_status !== 'completed' && (
                        <span className="text-[#8b5cf6]">{Math.round(m.transcription_progress || 0)}%</span>
                      )}
                    </div>
                    {m.attendees && m.attendees.length > 0 && (
                      <div className="flex items-center gap-1.5 mt-1.5 text-xs text-[#6b7280]">
                        <Users className="w-3 h-3 text-[#9ca3af]" />
                        <span className="truncate max-w-[400px]" title={m.attendees.join(', ')}>
                          {m.attendees.length} attendee{m.attendees.length > 1 ? 's' : ''}: {m.attendees.slice(0, 3).join(', ')}{m.attendees.length > 3 ? ` +${m.attendees.length - 3}` : ''}
                        </span>
                      </div>
                    )}
                    {m.error_message && <p className="text-xs text-[#ef4444] mt-1">{m.error_message}</p>}
                  </div>

                  <div className="flex items-center gap-1 ml-3 shrink-0">
                    {m.transcription_id && m.transcription_status === 'completed' && (
                      <>
                        <button onClick={() => navigate(`/transcriptions/${m.transcription_id}`)}
                          className="px-3 py-1.5 text-xs bg-[#2563eb] text-white rounded hover:bg-[#1d4ed8] transition-colors">
                          ดูผล
                        </button>
                        <button onClick={async () => { const g = await getGroups(); setGroups(g); openProcessModal(m, 'retranscribe'); }}
                          className="px-3 py-1.5 text-xs border border-[#d1d5db] text-[#374151] rounded hover:bg-[#f3f4f6] transition-colors">
                          ถอดเสียงใหม่
                        </button>
                      </>
                    )}
                    {m.audio_file_id && (
                      <button onClick={() => handleDownload(m)} title="ดาวน์โหลดไฟล์เสียง"
                        className="p-1.5 text-[#6b7280] hover:text-[#2563eb] transition-colors">
                        <Download className="w-4 h-4" />
                      </button>
                    )}
                    {(m.status === 'discovered' || m.status === 'skipped') && (
                      <button onClick={async () => { const g = await getGroups(); setGroups(g); openProcessModal(m, 'process'); }}
                        className="px-3 py-1.5 text-xs bg-[#2563eb] text-white rounded hover:bg-[#1d4ed8] transition-colors">
                        ถอดเสียง
                      </button>
                    )}
                    {(m.status === 'queued' || m.status === 'failed') && (
                      <button onClick={() => handleRetry(m.id)} title="ลองใหม่"
                        className="p-1.5 text-[#6b7280] hover:text-[#f59e0b] transition-colors">
                        <RotateCcw className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {processTarget && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setProcessTarget(null)}>
          <div className="bg-white rounded-xl p-6 w-[400px] shadow-2xl" onClick={e => e.stopPropagation()}>
            <h3 className="font-semibold mb-1">{processMode === 'retranscribe' ? 'ถอดเสียงใหม่' : 'ถอดเสียง'}</h3>
            <p className="text-sm text-[#6b7280] mb-4">{processTarget.meeting_subject || 'recording'}</p>
            {processMode === 'retranscribe' && (
              <p className="text-xs text-[#f59e0b] mb-3">⚠️ ข้อมูลถอดเสียงและ MoM ปัจจุบันจะถูกเขียนทับ</p>
            )}
            <div className="space-y-3 mb-4">
              <div>
                <label className="block text-sm font-medium text-[#374151] mb-1">กลุ่ม</label>
                <select value={selectedGroup} onChange={e => setSelectedGroup(e.target.value)}
                  className="w-full px-3 py-2 border border-[#d1d5db] rounded-lg text-sm focus:outline-none focus:border-[#2563eb]">
                  <option value="">ทั่วไป (default)</option>
                  {groups.filter(g => !g.is_default).map(g => (
                    <option key={g.id} value={g.id}>{g.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#374151] mb-1">Diarization (แยกผู้พูด)</label>
                <select value={selectedDiarization} onChange={e => setSelectedDiarization(e.target.value)}
                  className="w-full px-3 py-2 border border-[#d1d5db] rounded-lg text-sm focus:outline-none focus:border-[#2563eb]">
                  <option value="smart">อัตโนมัติ (แนะนำ)</option>
                  <option value="spectral">Spectral Clustering (Deepgram + Local GPU)</option>
                  <option value="deepgram">Deepgram Nova-3 (API)</option>
                  <option value="pyannote">Pyannote (Local GPU)</option>
                  <option value="gemini">Gemini 2.5 Flash (API)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[#374151] mb-1">Transcription (ถอดคำ)</label>
                <select value={selectedTranscription} onChange={e => setSelectedTranscription(e.target.value)}
                  className="w-full px-3 py-2 border border-[#d1d5db] rounded-lg text-sm focus:outline-none focus:border-[#2563eb]">
                  <option value="gemini">Gemini 2.5 Flash (API)</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button onClick={() => setProcessTarget(null)} className="px-4 py-2 text-sm text-[#6b7280] hover:bg-[#f3f4f6] rounded-lg">ยกเลิก</button>
              <button onClick={handleProcess} className="px-4 py-2 text-sm bg-[#2563eb] text-white rounded-lg hover:bg-[#1d4ed8]">
                {processMode === 'retranscribe' ? 'เริ่มถอดเสียงใหม่' : 'เริ่มถอดเสียง'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

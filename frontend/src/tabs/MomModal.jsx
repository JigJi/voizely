import { useState, useEffect, useRef } from 'react';
import { X, Pencil, RefreshCw, Download, Check, XCircle, Loader2 } from 'lucide-react';
import { marked } from 'marked';
import { saveMomFull, regenerateMom, exportDocxUrl } from '../api';
import { notify } from '../components/Notification';
import Modal from '../components/Modal';
import { getToken } from '../lib/auth';

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

/** Parse MoM markdown into sections */
function parseSections(content) {
  if (!content) return [];
  const lines = content.split('\n');
  const sections = [];
  let current = null;

  for (const line of lines) {
    if (line.startsWith('### ')) {
      if (current) sections.push(current);
      current = { title: line.replace('### ', '').trim(), lines: [] };
    } else if (current) {
      current.lines.push(line);
    }
  }
  if (current) sections.push(current);

  return sections.map(s => ({
    title: s.title,
    content: s.lines.join('\n').trim(),
  }));
}

/** Parse info section content into key-value pairs */
function parseInfoFields(content) {
  const fields = {};
  for (const line of content.split('\n')) {
    const match = line.match(/^-\s*\*\*(.+?):\*\*\s*(.*)$/);
    if (match) {
      fields[match[1].trim()] = match[2].trim();
    }
  }
  return fields;
}

/** Rebuild info section from key-value pairs */
function buildInfoContent(fields) {
  return Object.entries(fields).map(([k, v]) => `- **${k}:** ${v}`).join('\n');
}

/** Rebuild full markdown from sections */
function buildContent(sections) {
  return sections.map(s => `### ${s.title}\n${s.content}`).join('\n\n');
}

/** Render markdown to HTML */
function renderMd(md) {
  marked.setOptions({ gfm: true, breaks: true });
  return marked.parse(convertMdTables(md));
}

/** Info section as form fields */
function InfoSection({ section, onSave }) {
  const [editing, setEditing] = useState(false);
  const [fields, setFields] = useState(() => parseInfoFields(section.content));

  useEffect(() => {
    setFields(parseInfoFields(section.content));
  }, [section.content]);

  function handleSave() {
    onSave(buildInfoContent(fields));
    setEditing(false);
  }

  const fieldLabels = Object.keys(fields);

  return (
    <div className="mb-5">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-[#374151]">{section.title}</h3>
        {!editing ? (
          <button onClick={() => setEditing(true)} className="flex items-center gap-1 px-2 py-1 text-xs text-[#6b7280] hover:text-[#2563eb] hover:bg-[#f3f4f6] rounded transition-colors">
            <Pencil className="w-3 h-3" /> แก้ไข
          </button>
        ) : (
          <div className="flex items-center gap-1">
            <button onClick={handleSave} className="flex items-center gap-1 px-2 py-1 text-xs text-white bg-[#2563eb] hover:bg-[#1d4ed8] rounded transition-colors">
              <Check className="w-3 h-3" /> บันทึก
            </button>
            <button onClick={() => { setFields(parseInfoFields(section.content)); setEditing(false); }} className="flex items-center gap-1 px-2 py-1 text-xs text-[#6b7280] hover:bg-[#f3f4f6] rounded transition-colors">
              <XCircle className="w-3 h-3" /> ยกเลิก
            </button>
          </div>
        )}
      </div>

      {editing ? (
        <div className="space-y-2">
          {fieldLabels.map(key => (
            <div key={key} className="flex items-center gap-3">
              <label className="text-xs text-[#6b7280] w-24 shrink-0 text-right">{key}</label>
              <input
                type="text"
                value={fields[key] || ''}
                onChange={e => setFields({ ...fields, [key]: e.target.value })}
                className="flex-1 px-3 py-1.5 border border-[#d1d5db] rounded text-sm focus:outline-none focus:border-[#2563eb]"
              />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-1">
          {fieldLabels.map(key => (
            <div key={key} className="flex items-center gap-2 text-sm">
              <span className="text-[#6b7280] w-24 shrink-0 text-right">{key}:</span>
              <span className="text-[#374151]">{fields[key]}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Content section with markdown render + plain text edit */
function ContentSection({ section, onSave }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(section.content);
  const viewRef = useRef();

  useEffect(() => {
    setDraft(section.content);
  }, [section.content]);

  useEffect(() => {
    if (viewRef.current && !editing) {
      viewRef.current.innerHTML = renderMd(section.content);
    }
  }, [section.content, editing]);

  // Convert markdown to plain text for editing
  function mdToPlain(md) {
    return md
      .replace(/\*\*(.+?)\*\*/g, '$1')  // **bold** → bold
      .replace(/\*(.+?)\*/g, '$1');       // *italic* → italic
  }

  // Convert plain text back to markdown (preserve structure)
  function plainToMd(plain) {
    // Keep bullet structure, just return as-is (user edits plain text)
    return plain;
  }

  function handleSave() {
    onSave(plainToMd(draft));
    setEditing(false);
  }

  return (
    <div className="mb-5">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-[#374151]">{section.title}</h3>
        {!editing ? (
          <button onClick={() => { setDraft(mdToPlain(section.content)); setEditing(true); }} className="flex items-center gap-1 px-2 py-1 text-xs text-[#6b7280] hover:text-[#2563eb] hover:bg-[#f3f4f6] rounded transition-colors">
            <Pencil className="w-3 h-3" /> แก้ไข
          </button>
        ) : (
          <div className="flex items-center gap-1">
            <button onClick={handleSave} className="flex items-center gap-1 px-2 py-1 text-xs text-white bg-[#2563eb] hover:bg-[#1d4ed8] rounded transition-colors">
              <Check className="w-3 h-3" /> บันทึก
            </button>
            <button onClick={() => { setDraft(section.content); setEditing(false); }} className="flex items-center gap-1 px-2 py-1 text-xs text-[#6b7280] hover:bg-[#f3f4f6] rounded transition-colors">
              <XCircle className="w-3 h-3" /> ยกเลิก
            </button>
          </div>
        )}
      </div>

      {editing ? (
        <textarea
          value={draft}
          onChange={e => setDraft(e.target.value)}
          className="w-full min-h-[120px] p-3 border border-[#d1d5db] rounded-lg text-sm focus:outline-none focus:border-[#2563eb] resize-y leading-relaxed"
          rows={Math.max(5, draft.split('\n').length + 2)}
        />
      ) : (
        <div ref={viewRef} className="prose prose-sm max-w-none mom-content" />
      )}
    </div>
  );
}

/** Parse markdown table rows into array of objects */
function parseTableRows(content) {
  const lines = content.split('\n').filter(l => l.trim().startsWith('|'));
  if (lines.length < 2) return [];
  // Skip header + separator
  const dataLines = lines.filter(l => !/^[\s|:-]+$/.test(l.replace(/\|/g, '').trim()));
  // Skip the header row (first line with actual text)
  const rows = [];
  for (let i = 1; i < dataLines.length; i++) {
    const cells = dataLines[i].split('|').filter(c => c.trim()).map(c => c.trim());
    if (cells.length >= 4) {
      rows.push({ no: cells[0], task: cells[1], deadline: cells[2], owner: cells[3] });
    }
  }
  // If parsing gave 0 rows, try without skipping header
  if (rows.length === 0) {
    for (const line of dataLines) {
      const cells = line.split('|').filter(c => c.trim()).map(c => c.trim());
      if (cells.length >= 4 && cells[0] !== 'ลำดับ') {
        rows.push({ no: cells[0], task: cells[1], deadline: cells[2], owner: cells[3] });
      }
    }
  }
  return rows;
}

/** Build markdown table from rows */
function buildTableContent(rows) {
  if (rows.length === 0) return 'ไม่มี';
  let md = '| ลำดับ | รายละเอียด | กำหนดการ | ผู้รับผิดชอบ |\n';
  md += '|------|-----------|---------|------------|\n';
  rows.forEach((r, i) => {
    md += `| ${i + 1} | ${r.task} | ${r.deadline} | ${r.owner} |\n`;
  });
  return md.trim();
}

/** Action items table editor */
function ActionTableSection({ section, onSave, speakers }) {
  const [editing, setEditing] = useState(false);
  const [rows, setRows] = useState(() => parseTableRows(section.content));
  const viewRef = useRef();

  useEffect(() => {
    setRows(parseTableRows(section.content));
  }, [section.content]);

  useEffect(() => {
    if (viewRef.current) {
      if (!editing) {
        viewRef.current.innerHTML = renderMd(section.content);
      } else {
        viewRef.current.innerHTML = '';
      }
    }
  }, [section.content, editing]);

  function updateRow(index, field, value) {
    setRows(rows.map((r, i) => i === index ? { ...r, [field]: value } : r));
  }

  function addRow() {
    setRows([...rows, { no: '', task: '', deadline: 'TBC', owner: speakers[0] || '' }]);
  }

  function removeRow(index) {
    setRows(rows.filter((_, i) => i !== index));
  }

  function handleSave() {
    onSave(buildTableContent(rows));
    setEditing(false);
  }

  function handleCancel() {
    setRows(parseTableRows(section.content));
    setEditing(false);
  }

  return (
    <div className="mb-5">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-[#374151]">{section.title}</h3>
        {!editing ? (
          <button onClick={() => setEditing(true)} className="flex items-center gap-1 px-2 py-1 text-xs text-[#6b7280] hover:text-[#2563eb] hover:bg-[#f3f4f6] rounded transition-colors">
            <Pencil className="w-3 h-3" /> แก้ไข
          </button>
        ) : (
          <div className="flex items-center gap-1">
            <button onClick={handleSave} className="flex items-center gap-1 px-2 py-1 text-xs text-white bg-[#2563eb] hover:bg-[#1d4ed8] rounded transition-colors">
              <Check className="w-3 h-3" /> บันทึก
            </button>
            <button onClick={handleCancel} className="flex items-center gap-1 px-2 py-1 text-xs text-[#6b7280] hover:bg-[#f3f4f6] rounded transition-colors">
              <XCircle className="w-3 h-3" /> ยกเลิก
            </button>
          </div>
        )}
      </div>

      {editing && (
        <div>
          <table className="w-full text-sm border border-[#e5e7eb] rounded-lg overflow-hidden">
            <thead>
              <tr className="bg-[#f9fafb]">
                <th className="px-2 py-2 text-left text-xs font-medium text-[#6b7280] w-8">#</th>
                <th className="px-2 py-2 text-left text-xs font-medium text-[#6b7280]">รายละเอียด</th>
                <th className="px-2 py-2 text-left text-xs font-medium text-[#6b7280] w-28">กำหนดการ</th>
                <th className="px-2 py-2 text-left text-xs font-medium text-[#6b7280] w-28">ผู้รับผิดชอบ</th>
                <th className="px-2 py-2 w-8"></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className="border-t border-[#e5e7eb]">
                  <td className="px-2 py-1.5 text-xs text-[#9ca3af]">{i + 1}</td>
                  <td className="px-1 py-1">
                    <input
                      value={row.task}
                      onChange={e => updateRow(i, 'task', e.target.value)}
                      className="w-full px-2 py-1 text-sm border border-[#e5e7eb] rounded focus:outline-none focus:border-[#2563eb]"
                    />
                  </td>
                  <td className="px-1 py-1">
                    <input
                      value={row.deadline}
                      onChange={e => updateRow(i, 'deadline', e.target.value)}
                      className="w-full px-2 py-1 text-sm border border-[#e5e7eb] rounded focus:outline-none focus:border-[#2563eb]"
                    />
                  </td>
                  <td className="px-1 py-1">
                    <select
                      value={row.owner}
                      onChange={e => updateRow(i, 'owner', e.target.value)}
                      className="w-full px-2 py-1 text-sm border border-[#e5e7eb] rounded focus:outline-none focus:border-[#2563eb]"
                    >
                      {speakers.map(s => <option key={s} value={s}>{s}</option>)}
                      <option value="">-- ไม่ระบุ --</option>
                    </select>
                  </td>
                  <td className="px-1 py-1">
                    <button onClick={() => removeRow(i)} className="p-1 text-[#9ca3af] hover:text-[#ef4444] transition-colors">
                      <XCircle className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button onClick={addRow} className="mt-2 px-3 py-1.5 text-xs text-[#2563eb] hover:bg-[#eff6ff] rounded transition-colors">
            + เพิ่มรายการ
          </button>
        </div>
      )}
      {!editing && (
        <div ref={viewRef} className="prose prose-sm max-w-none mom-content" />
      )}
    </div>
  );
}

export default function MomModal({ transcription, onClose, onUpdate }) {
  const [sections, setSections] = useState([]);
  const [showRegen, setShowRegen] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  useEffect(() => {
    const content = transcription.mom_full || transcription.summary || '';
    setSections(parseSections(content));
  }, [transcription]);

  async function handleSectionSave(index, newContent) {
    const updated = sections.map((s, i) => i === index ? { ...s, content: newContent } : s);
    setSections(updated);
    const fullContent = buildContent(updated);
    await saveMomFull(transcription.id, fullContent);
    notify('บันทึกแล้ว');
    onUpdate?.();
  }

  async function handleRegenerate() {
    setShowRegen(false);
    setRegenerating(true);
    try {
      await regenerateMom(transcription.id);
      onUpdate?.();
      notify('สร้าง MoM ใหม่แล้ว');
      const res = await fetch(`/api/transcriptions/${transcription.id}`, { headers: { Authorization: `Bearer ${getToken()}` } });
      const data = await res.json();
      setSections(parseSections(data.mom_full || data.summary || ''));
    } finally { setRegenerating(false); }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-white rounded-xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-xl" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#e5e7eb]">
          <h2 className="text-base font-semibold">Minutes of Meeting</h2>
          <div className="flex items-center gap-2">
            <a href={`${exportDocxUrl(transcription.id)}?token=${localStorage.getItem('token')}`} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[#2563eb] text-white rounded-lg hover:bg-[#1d4ed8] transition-colors">
              <Download className="w-3.5 h-3.5" /> Export
            </a>
            <button disabled={regenerating} onClick={() => setShowRegen(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-[#d1d5db] rounded-lg hover:bg-[#f3f4f6] transition-colors disabled:opacity-50">
              {regenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
              {regenerating ? 'กำลังสร้าง...' : 'Regenerate'}
            </button>
            <button onClick={onClose} className="p-1.5 hover:bg-[#f3f4f6] rounded-lg transition-colors">
              <X className="w-4 h-4 text-[#9ca3af]" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto p-6">
          {sections.length === 0 ? (
            <p className="text-sm text-[#9ca3af]">ยังไม่มี MoM</p>
          ) : (
            sections.map((section, i) => {
              if (section.title === 'ข้อมูลการประชุม') {
                return (
                  <InfoSection
                    key={`${section.title}-${i}`}
                    section={section}
                    onSave={(newContent) => handleSectionSave(i, newContent)}
                  />
                );
              }
              if (section.title === 'สิ่งที่ต้องทำ') {
                const speakers = (transcription.segments || [])
                  .map(s => s.speaker).filter(Boolean)
                  .filter((v, i, a) => a.indexOf(v) === i);
                return (
                  <ActionTableSection
                    key={`${section.title}-${i}`}
                    section={section}
                    speakers={speakers}
                    onSave={(newContent) => handleSectionSave(i, newContent)}
                  />
                );
              }
              return (
                <ContentSection
                  key={`${section.title}-${i}`}
                  section={section}
                  onSave={(newContent) => handleSectionSave(i, newContent)}
                />
              );
            })
          )}
        </div>
      </div>

      {showRegen && (
        <Modal title="สร้าง MoM ใหม่?" message="ระบบจะสร้าง MoM ใหม่จาก transcript ปัจจุบัน" okText="สร้างใหม่" onConfirm={handleRegenerate} onCancel={() => setShowRegen(false)} />
      )}
    </div>
  );
}

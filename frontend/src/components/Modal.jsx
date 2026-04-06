import { useState, useRef, useEffect } from 'react';

export default function Modal({ title, message, type = 'confirm', placeholder, okText = 'ตกลง', danger, onConfirm, onCancel }) {
  const [value, setValue] = useState('');
  const inputRef = useRef();

  useEffect(() => {
    if (type === 'prompt' && inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  function handleOk() {
    if (type === 'prompt') onConfirm?.(value.trim());
    else onConfirm?.();
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center" onClick={onCancel}>
      <div className="bg-white rounded-xl p-6 min-w-[360px] max-w-[480px] shadow-lg" onClick={e => e.stopPropagation()}>
        {title && <div className="text-base font-semibold mb-2">{title}</div>}
        {message && <div className="text-sm text-[#6b7280] mb-4">{message}</div>}
        {type === 'prompt' && (
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={e => setValue(e.target.value)}
            placeholder={placeholder}
            className="w-full px-3 py-2.5 border border-[#d1d5db] rounded-lg text-sm mb-4 focus:outline-none focus:border-[#2563eb] focus:ring-1 focus:ring-[#2563eb]"
            onKeyDown={e => { if (e.key === 'Enter') handleOk(); if (e.key === 'Escape') onCancel?.(); }}
          />
        )}
        <div className="flex gap-2 justify-end">
          {type !== 'alert' && (
            <button onClick={onCancel} className="px-4 py-2 text-sm border border-[#d1d5db] rounded-lg hover:bg-[#f3f4f6] transition-colors">
              ยกเลิก
            </button>
          )}
          <button
            onClick={handleOk}
            className={`px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors ${
              danger ? 'bg-[#ef4444] hover:bg-[#dc2626]' : 'bg-[#2563eb] hover:bg-[#1d4ed8]'
            }`}
          >
            {okText}
          </button>
        </div>
      </div>
    </div>
  );
}

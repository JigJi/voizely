import { useState, useRef, useEffect } from 'react';
import { LogOut, ChevronDown, User } from 'lucide-react';
import { getUser, logout } from '../lib/auth';

export default function Header() {
  const [open, setOpen] = useState(false);
  const ref = useRef();
  const user = getUser();

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  if (!user) return null;

  const initial = (user.first_name || user.username || '?')[0].toUpperCase();
  const displayName = user.first_name
    ? `${user.first_name}${user.last_name ? ' ' + user.last_name : ''}`
    : user.username;

  return (
    <header className="h-12 bg-white border-b border-[#e5e7eb] flex items-center justify-end px-4 shrink-0">
      {/* User dropdown */}
      <div className="relative" ref={ref}>
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-[#f3f4f6] transition-colors"
        >
          <div className="w-7 h-7 rounded-full bg-[#2563eb] text-white flex items-center justify-center text-xs font-medium">
            {initial}
          </div>
          <span className="text-sm text-[#374151] font-medium max-w-[150px] truncate">{displayName}</span>
          <ChevronDown className={`w-3.5 h-3.5 text-[#9ca3af] transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>

        {open && (
          <div className="absolute right-0 top-full mt-1 w-56 bg-white rounded-lg shadow-lg border border-[#e5e7eb] py-1 z-50">
            {/* User info */}
            <div className="px-4 py-3 border-b border-[#e5e7eb]">
              <div className="text-sm font-medium text-[#1f2937]">{displayName}</div>
              {user.department && (
                <div className="text-xs text-[#9ca3af] mt-0.5">{user.department}</div>
              )}
              {user.role && (
                <div className="text-xs text-[#9ca3af]">{user.role}</div>
              )}
            </div>
            {/* Actions */}
            <button
              onClick={logout}
              className="flex items-center gap-2.5 w-full px-4 py-2.5 text-sm text-[#6b7280] hover:text-[#ef4444] hover:bg-[#fef2f2] transition-colors"
            >
              <LogOut className="w-4 h-4" />
              <span>ออกจากระบบ</span>
            </button>
          </div>
        )}
      </div>
    </header>
  );
}

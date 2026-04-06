import { useState, useEffect } from 'react';

let showFn = null;

export function notify(message, type = 'success') {
  showFn?.({ message, type });
}

export default function NotificationContainer() {
  const [toast, setToast] = useState(null);

  useEffect(() => {
    showFn = (t) => {
      setToast(t);
      setTimeout(() => setToast(null), 3000);
    };
    return () => { showFn = null; };
  }, []);

  if (!toast) return null;

  const bg = toast.type === 'success' ? 'bg-[#22c55e]' : toast.type === 'error' ? 'bg-[#ef4444]' : 'bg-[#3b82f6]';

  return (
    <div className={`fixed top-5 left-1/2 -translate-x-1/2 z-[9999] px-5 py-2.5 rounded-lg text-white text-sm font-medium shadow-lg ${bg} transition-opacity`}>
      {toast.message}
    </div>
  );
}

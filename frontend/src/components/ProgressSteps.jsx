import { useState, useEffect, useRef } from 'react';
import { Check } from 'lucide-react';

const STEPS_DEFAULT = [
  { pct: 5,  name: 'ถอดเสียง',    sub: 'Deepgram' },
  { pct: 30, name: 'แยกผู้พูด',   sub: 'Diarization' },
  { pct: 50, name: 'แก้ไขข้อความ', sub: 'Gemini' },
  { pct: 85, name: 'สรุป MoM',    sub: 'Analysis' },
];

const STEPS_WITH_UPLOAD = [
  { pct: -1, name: 'อัพโหลดไฟล์', sub: 'Upload', isUpload: true },
  ...STEPS_DEFAULT,
];

export default function ProgressSteps({ progress = 0, statusMessage = '', showUpload = false, uploadPercent = null }) {
  const STEPS = showUpload ? STEPS_WITH_UPLOAD : STEPS_DEFAULT;
  const uploadDone = uploadPercent !== null && uploadPercent >= 100;

  const [displayProgress, setDisplayProgress] = useState(progress);
  const maxRef = useRef(progress);
  const timerRef = useRef(null);

  useEffect(() => {
    const target = Math.max(progress, maxRef.current);
    maxRef.current = target;

    if (timerRef.current) clearInterval(timerRef.current);
    if (target > displayProgress) {
      timerRef.current = setInterval(() => {
        setDisplayProgress(prev => {
          if (prev >= target - 0.5) { clearInterval(timerRef.current); return target; }
          return prev + 0.3;
        });
      }, 100);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [progress]);

  function getStepState(step, i) {
    if (step.isUpload) {
      const done = uploadDone;
      const active = !done && uploadPercent !== null;
      return { done, active };
    }
    const done = displayProgress >= step.pct;
    const prevStep = STEPS[i - 1];
    const prevPct = prevStep?.isUpload ? 0 : (prevStep?.pct ?? 0);
    const active = !done && displayProgress >= prevPct && uploadDone !== false;
    return { done, active: uploadDone === false ? false : active };
  }

  const isUploading = showUpload && uploadPercent !== null && !uploadDone;
  const displayValue = isUploading ? uploadPercent : Math.round(displayProgress);
  const displayLabel = isUploading ? 'กำลังอัพโหลด...' : 'กรุณารอสักครู่';

  return (
    <div className="flex items-center justify-center h-full">
      <div className="w-full max-w-2xl px-12">
        {/* Timeline */}
        <div className="relative flex items-center justify-between">
          {/* Lines between nodes */}
          {STEPS.map((step, i) => {
            if (i === 0) return null;
            const prev = getStepState(STEPS[i - 1], i - 1);
            const cur = getStepState(step, i);

            const nodeWidth = 100 / STEPS.length;
            const segLeft = ((i - 1) / STEPS.length) * 100 + nodeWidth / 2;
            const segWidth = nodeWidth;

            const showLine = (prev.done && cur.done) || (prev.done && !cur.done);

            return (
              <div key={`line-${i}`} className="absolute top-5 h-0.5"
                style={{ left: `${segLeft}%`, width: `${segWidth}%` }}>
                <div className="h-full bg-[#e5e7eb] w-full" />
                {showLine && (
                  <div className="absolute inset-0 h-full bg-[#2563eb]" />
                )}
              </div>
            );
          })}

          {STEPS.map((step, i) => {
            const { done, active } = getStepState(step, i);

            return (
              <div key={i} className="relative z-10 flex flex-col items-center" style={{ width: `${100 / STEPS.length}%` }}>
                <div className="relative">
                  {active && (
                    <div className="absolute inset-0 rounded-full bg-[#2563eb] animate-ping opacity-30" />
                  )}
                  <div className={`relative w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-500 ${
                    done
                      ? 'bg-[#22c55e] text-white'
                      : active
                      ? 'bg-[#2563eb] text-white shadow-lg shadow-blue-300/50'
                      : 'bg-white border-2 border-[#e5e7eb] text-[#9ca3af]'
                  }`}>
                    {done ? <Check className="w-5 h-5" strokeWidth={3} /> : <span>{i + 1}</span>}
                  </div>
                </div>

                <div className="mt-3 text-center">
                  <div className={`text-sm font-medium transition-colors duration-300 ${
                    done ? 'text-[#22c55e]' : active ? 'text-[#2563eb]' : 'text-[#9ca3af]'
                  }`}>{step.name}</div>
                  <div className={`text-xs mt-0.5 transition-colors duration-300 ${
                    active ? 'text-[#93b4f5]' : 'text-[#d1d5db]'
                  }`}>{step.sub}</div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="text-center mt-12">
          <div className="text-4xl font-bold text-[#2563eb] tabular-nums">{displayValue}%</div>
          <div className="text-sm text-[#9ca3af] mt-1">{displayLabel}</div>
        </div>

      </div>
    </div>
  );
}

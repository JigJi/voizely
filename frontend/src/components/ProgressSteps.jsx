import { Check } from 'lucide-react';

const STEPS = [
  { pct: 10, name: 'แยกผู้พูด', sub: 'Diarization' },
  { pct: 20, name: 'จับคู่เสียง', sub: 'Voiceprint' },
  { pct: 30, name: 'ถอดเสียง', sub: 'Transcription' },
  { pct: 95, name: 'สรุป MoM', sub: 'Analysis' },
];

export default function ProgressSteps({ progress = 0 }) {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="w-full max-w-2xl px-12">
        {/* Timeline */}
        <div className="relative flex items-center justify-between">
          {/* Lines between nodes */}
          {STEPS.map((step, i) => {
            if (i === 0) return null;
            const prevDone = progress > STEPS[i - 1].pct;
            const curDone = progress > step.pct;
            const curActive = progress >= step.pct - 10 && progress <= step.pct;
            const lineActive = prevDone && (curDone || curActive);

            return (
              <div key={`line-${i}`} className="absolute top-5 h-0.5 overflow-hidden"
                style={{
                  left: `${((i - 1) / (STEPS.length - 1)) * 100 + (50 / STEPS.length)}%`,
                  width: `${(1 / (STEPS.length - 1)) * 100 - (100 / STEPS.length)}%`,
                }}>
                <div className="h-full bg-[#e5e7eb] w-full" />
                {lineActive && (
                  <div className="absolute inset-0 h-full bg-[#2563eb] origin-left"
                    style={{
                      animation: curActive ? 'lineGrow 2s ease-in-out infinite' : 'none',
                      width: curDone ? '100%' : undefined,
                    }} />
                )}
                {prevDone && !curActive && !curDone && (
                  <div className="absolute inset-0 h-full bg-[#2563eb] origin-left" style={{ width: '0%' }} />
                )}
              </div>
            );
          })}

          {STEPS.map((step, i) => {
            const done = progress > step.pct;
            const active = progress >= step.pct - 10 && progress <= step.pct;

            return (
              <div key={i} className="relative z-10 flex flex-col items-center" style={{ width: `${100 / STEPS.length}%` }}>
                <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold transition-all duration-500 ${
                  done
                    ? 'bg-[#22c55e] text-white'
                    : active
                    ? 'bg-[#2563eb] text-white shadow-lg shadow-blue-200'
                    : 'bg-white border-2 border-[#e5e7eb] text-[#9ca3af]'
                }`}>
                  {done ? <Check className="w-5 h-5" strokeWidth={3} /> : <span>{i + 1}</span>}
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
          <div className="text-4xl font-bold text-[#2563eb] tabular-nums">{Math.round(progress)}%</div>
          <div className="text-sm text-[#9ca3af] mt-1">กรุณารอสักครู่</div>
        </div>

        <style>{`
          @keyframes lineGrow {
            0% { width: 0%; }
            50% { width: 100%; }
            100% { width: 0%; }
          }
        `}</style>
      </div>
    </div>
  );
}

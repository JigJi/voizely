import { useState, useEffect, useRef } from 'react';
import { Mic, Users, FileText, Shield, ChevronRight, Check, Headphones, BrainCircuit, Building2, Menu, X, Star, ArrowRight, Lock, UserCheck, MessageSquareQuote, ChevronDown } from 'lucide-react';

/* ──────────────────────── Scroll Animation ──────────────────────── */

function useReveal(opts = {}) {
  const ref = useRef(null);
  const [vis, setVis] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVis(true); obs.unobserve(el); } },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px', ...opts }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return { ref, vis };
}

function Reveal({ children, className = '', delay = 0, direction = 'up' }) {
  const { ref, vis } = useReveal();
  const t = { up: '0,50px,0', down: '0,-50px,0', left: '50px,0,0', right: '-50px,0,0', none: '0,0,0' };
  return (
    <div ref={ref} className={className} style={{
      opacity: vis ? 1 : 0,
      transform: vis ? 'translate3d(0,0,0)' : `translate3d(${t[direction]})`,
      transition: `opacity 0.8s cubic-bezier(.16,1,.3,1) ${delay}s, transform 0.8s cubic-bezier(.16,1,.3,1) ${delay}s`,
    }}>{children}</div>
  );
}

function Stagger({ children, className = '', gap = 0.1 }) {
  const { ref, vis } = useReveal();
  const items = Array.isArray(children) ? children : [children];
  return (
    <div ref={ref} className={className}>
      {items.map((c, i) => (
        <div key={i} style={{
          opacity: vis ? 1 : 0,
          transform: vis ? 'translate3d(0,0,0)' : 'translate3d(0,40px,0)',
          transition: `opacity .7s cubic-bezier(.16,1,.3,1) ${i * gap}s, transform .7s cubic-bezier(.16,1,.3,1) ${i * gap}s`,
        }}>{c}</div>
      ))}
    </div>
  );
}

/* ──────────────────────── People Bubble ──────────────────────── */

function PeopleBubble({ img, quotes, side, position, delay = 0 }) {
  const [idx, setIdx] = useState(0);
  const [phase, setPhase] = useState('wait'); // wait | typing | pause | fadeout
  const textRef = useRef(null);
  const [fullWidth, setFullWidth] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => setPhase('typing'), delay);
    return () => clearTimeout(t);
  }, [delay]);

  useEffect(() => {
    if (phase === 'typing') {
      // measure full width
      if (textRef.current) {
        textRef.current.style.maxWidth = 'none';
        setFullWidth(textRef.current.scrollWidth);
        textRef.current.style.maxWidth = '0px';
        requestAnimationFrame(() => {
          if (textRef.current) textRef.current.style.maxWidth = fullWidth + 20 + 'px';
        });
      }
      const t = setTimeout(() => setPhase('pause'), 1500);
      return () => clearTimeout(t);
    } else if (phase === 'pause') {
      const wait = 1500 + Math.random() * 1500;
      const t = setTimeout(() => setPhase('fadeout'), wait);
      return () => clearTimeout(t);
    } else if (phase === 'fadeout') {
      const t = setTimeout(() => {
        setIdx(prev => (prev + 1) % quotes.length);
        setPhase('typing');
      }, 400);
      return () => clearTimeout(t);
    }
  }, [phase, idx, quotes, fullWidth]);

  const display = quotes[idx];

  return (
    <div className="relative flex-1">
      <img src={img} alt="" className="w-full h-full object-cover rounded-2xl shadow-lg shadow-indigo-100/30" />
      <div className={`absolute z-50 ${position === 'center' ? 'top-1/2 -translate-y-1/2' : 'bottom-4'} ${side === 'right' ? 'left-[60%]' : 'right-[60%]'}`}>
        <div className="relative bg-white rounded-2xl px-3 py-2 shadow-md border border-gray-100 whitespace-nowrap">
          <p ref={textRef} className="text-[10px] text-[#5A5D8D] leading-snug overflow-hidden transition-all duration-[1.2s] ease-out"
            style={{ maxWidth: phase === 'wait' ? 0 : phase === 'fadeout' ? 0 : undefined, opacity: phase === 'fadeout' || phase === 'wait' ? 0 : 1, transition: 'max-width 1.2s ease-out, opacity 0.3s ease' }}>
            {display}
          </p>
          {/* Speech tail */}
          <svg className={`absolute top-1/2 -translate-y-1/2 ${side === 'right' ? 'right-full' : 'left-full'}`} width="8" height="12" viewBox="0 0 8 12" fill="none">
            {side === 'right' ? (
              <><path d="M8 0 L0 6 L8 12" fill="white" /><path d="M8 0 L0 6 L8 12" stroke="#e5e7eb" strokeWidth="1" fill="none" /><path d="M8 0.5 L8 11.5" stroke="white" strokeWidth="2" /></>
            ) : (
              <><path d="M0 0 L8 6 L0 12" fill="white" /><path d="M0 0 L8 6 L0 12" stroke="#e5e7eb" strokeWidth="1" fill="none" /><path d="M0 0.5 L0 11.5" stroke="white" strokeWidth="2" /></>
            )}
          </svg>
        </div>
      </div>
    </div>
  );
}

/* ──────────────────────── Colors (tldv palette) ──────────────────────── */
// Navy heading: #0F0F3D   Accent: #4338CA (indigo-700)   Body text: #5A5D8D   Accent light: #8585FF

/* ──────────────────────── Navbar ──────────────────────── */

const NAV = [
  { label: 'ฟีเจอร์', href: '#features' },
  { label: 'วิธีใช้งาน', href: '#how-it-works' },
  { label: 'แพ็กเกจ', href: '#pricing' },
  { label: 'FAQ', href: '#faq' },
];

function Navbar() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', h, { passive: true });
    return () => window.removeEventListener('scroll', h);
  }, []);

  return (
    <nav className={`fixed top-0 w-full z-50 transition-all duration-300 ${scrolled ? 'bg-white/90 backdrop-blur-xl shadow-sm' : ''}`}>
      <div className="max-w-[1200px] mx-auto px-6 h-16 flex items-center justify-between">
        <a href="#" className="flex items-center group">
          <img src="/logo.png" alt="Voizely" className="h-8 group-hover:scale-105 transition-transform" />
        </a>
        <div className="hidden md:flex items-center gap-8">
          {NAV.map(l => (
            <a key={l.href} href={l.href} className="text-sm font-medium text-[#5A5D8D] hover:text-[#4338CA] transition-colors">{l.label}</a>
          ))}
          <a href="#contact" className="px-6 py-2.5 text-sm font-semibold text-white bg-[#4338CA] rounded-full hover:bg-[#3730A3] hover:shadow-lg hover:shadow-indigo-200 hover:-translate-y-0.5 transition-all duration-300">เริ่มต้นใช้งานฟรี</a>
        </div>
        <button onClick={() => setOpen(!open)} className="md:hidden p-2 text-[#0F0F3D]">
          {open ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>
      {open && (
        <div className="md:hidden bg-white border-b border-gray-100 px-6 pb-4 space-y-3">
          {NAV.map(l => (
            <a key={l.href} href={l.href} onClick={() => setOpen(false)} className="block text-sm font-medium text-[#5A5D8D]">{l.label}</a>
          ))}
          <a href="#contact" onClick={() => setOpen(false)} className="block text-center px-5 py-2.5 text-sm font-semibold text-white bg-[#4338CA] rounded-full">เริ่มต้นใช้งานฟรี</a>
        </div>
      )}
    </nav>
  );
}

/* ──────────────────────── Hero (tldv style: pastel gradient bg) ──────────────────────── */

function Hero() {
  const [loaded, setLoaded] = useState(false);
  useEffect(() => { requestAnimationFrame(() => setLoaded(true)); }, []);

  const anim = (delay) => ({
    opacity: loaded ? 1 : 0,
    transform: loaded ? 'translateY(0)' : 'translateY(30px)',
    transition: `all 0.8s cubic-bezier(.16,1,.3,1) ${delay}s`,
  });

  return (
    <section className="relative pt-28 pb-32 overflow-hidden" style={{
      background: 'linear-gradient(160deg, #C4B5FD 0%, #D4C4FF 15%, #E0D0FF 30%, #F0C8E0 50%, #D8D0FE 65%, #C0CDFE 80%, #B8D8FE 100%)',
    }}>
      {/* Diagonal light beam like tldv */}
      <div className="absolute inset-0 pointer-events-none" style={{
        background: 'linear-gradient(135deg, transparent 0%, transparent 15%, rgba(255,255,255,0.55) 30%, rgba(255,255,255,0.85) 40%, rgba(255,255,255,0.55) 50%, transparent 65%, transparent 100%)',
      }} />
      {/* Vivid blobs for depth */}
      <div className="absolute top-0 left-[5%] w-[600px] h-[600px] rounded-full blur-[120px] pointer-events-none animate-[float_12s_ease-in-out_infinite]" style={{ background: 'rgba(139,92,246,0.25)' }} />
      <div className="absolute top-10 right-0 w-[500px] h-[500px] rounded-full blur-[120px] pointer-events-none animate-[float_15s_ease-in-out_infinite_reverse]" style={{ background: 'rgba(236,72,153,0.18)' }} />
      <div className="absolute bottom-0 left-[25%] w-[500px] h-[500px] rounded-full blur-[120px] pointer-events-none" style={{ background: 'rgba(56,189,248,0.15)' }} />

      <div className="max-w-[1200px] mx-auto px-6 text-center">
        <h1 className="text-5xl md:text-[64px] font-bold text-[#0F0F3D] leading-[1.15] tracking-tight mb-6" style={anim(0.2)}>
          AI ถอดเสียงและสรุปการประชุม<br />
          <span className="text-[#4338CA]">ที่องค์กรไว้วางใจ</span>
        </h1>

        <p className="text-lg text-[#5A5D8D] max-w-2xl mx-auto mb-10 leading-relaxed" style={anim(0.4)}>
          เชื่อมต่อทุกแพลตฟอร์มประชุม ถอดเสียง แยกผู้พูด สรุป MoM
          และร่างเอกสารให้อัตโนมัติ — ทุกอย่างครบจบในที่เดียว
        </p>


        {/* Trust badges row */}
        <div className="flex flex-wrap items-center justify-center gap-6 md:gap-8 mt-12" style={anim(0.8)}>
          <div className="flex items-center gap-1.5">
            {[...Array(5)].map((_, i) => (
              <Star key={i} className="w-4 h-4 text-amber-400 fill-amber-400" />
            ))}
            <span className="text-sm text-[#5A5D8D] ml-1 font-medium">4.9/5</span>
          </div>
          <div className="h-4 w-px bg-[#B0AED0]" />
          <span className="text-sm text-[#5A5D8D]">รองรับ <span className="font-bold text-[#0F0F3D]">100+</span> ภาษา</span>
          <div className="h-4 w-px bg-[#B0AED0]" />
          <span className="text-sm text-[#5A5D8D]">รองรับภาษาถิ่น <span className="font-bold text-[#0F0F3D]">เหนือ</span> <span className="font-bold text-[#0F0F3D]">อีสาน</span> <span className="font-bold text-[#0F0F3D]">ใต้</span></span>
        </div>

        {/* Product mockup — people + app */}
        <div className="mt-16 max-w-6xl mx-auto flex items-stretch gap-6 text-left" style={{ opacity: loaded ? 1 : 0, transform: loaded ? 'translateY(0)' : 'translateY(60px)', transition: 'all 1.2s cubic-bezier(.16,1,.3,1) 1s' }}>

          {/* People column — stretch to match app height */}
          <div className="hidden lg:flex flex-col gap-3 shrink-0 w-[160px]">
            {[
              { img: '/people1.png', quotes: ['สวัสดีค่ะ', 'วันนี้ขอเสนอ', 'ขอบคุณมากค่ะ'], side: 'right' },
              { img: '/people2.png', quotes: ['สบายดีเจ้า', 'มื้อนี้สิมาเว่า', 'แหลงเข้าใจหม้าย'], side: 'left' },
              { img: '/people3.png', quotes: ['Nice to meet you!', 'Let me explain...', 'Sounds good!'], side: 'right' },
            ].map((p, i) => (
              <PeopleBubble key={i} img={p.img} quotes={p.quotes} side={p.side} position={i === 0 ? 'center' : 'bottom'} delay={[0, 2500, 1200][i]} />
            ))}
          </div>

          {/* Main app window */}
          <div className="flex-1 rounded-2xl border border-white/60 bg-white/95 backdrop-blur-sm shadow-2xl shadow-indigo-200/40 overflow-hidden flex flex-col">
            {/* Title bar */}
            <div className="flex items-center gap-2 px-4 py-2.5 bg-[#F8F7FF] border-b border-gray-100/80">
              <div className="flex gap-1.5">
                <div className="w-3 h-3 rounded-full bg-[#FF6B6B]" />
                <div className="w-3 h-3 rounded-full bg-[#FFD93D]" />
                <div className="w-3 h-3 rounded-full bg-[#6BCB77]" />
              </div>
              <div className="flex-1 flex items-center justify-center gap-2">
                <div className="px-3 py-1 bg-white rounded-md text-xs text-[#B0AED0] border border-gray-100 flex items-center gap-1.5">
                  <Lock className="w-3 h-3" /> cappa.ai/transcriptions/247
                </div>
              </div>
            </div>

            <div className="flex">
              {/* Sidebar */}
              <div className="hidden md:block w-56 border-r border-gray-100 bg-[#FAFAFF] p-3 shrink-0">
                <div className="flex items-center gap-2 px-2 mb-3">
                  <img src="/logo.png" alt="Voizely" className="h-5" />
                </div>
                <div className="space-y-0.5">
                  {[
                    { name: 'ประชุมงบประมาณ Q2', active: true, status: 'done' },
                    { name: 'Weekly Standup #42', active: false, status: 'done' },
                    { name: 'Review UX Design', active: false, status: 'processing' },
                    { name: 'Board Meeting 03/28', active: false, status: 'done' },
                  ].map((f, i) => (
                    <div key={i} className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-[11px] ${f.active ? 'bg-indigo-50 text-[#4338CA] font-semibold' : 'text-[#5A5D8D]'}`}>
                      <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${f.status === 'done' ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'}`} />
                      <span className="truncate">{f.name}</span>
                    </div>
                  ))}
                </div>
                <div className="mt-4 pt-3 border-t border-gray-100">
                  <div className="flex items-center gap-2 px-2 py-1.5 text-[11px] text-[#B0AED0]">
                    <Users className="w-3.5 h-3.5" /> Speakers
                  </div>
                </div>
              </div>

              {/* Main content */}
              <div className="flex-1 min-w-0">
                {/* Meeting header */}
                <div className="px-5 py-3 border-b border-gray-50 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-[#0F0F3D]">ประชุมงบประมาณ Q2</h3>
                    <span className="text-[10px] text-[#B0AED0]">28 มี.ค. 2569 &middot; 45 นาที &middot; ผู้พูด 3 คน</span>
                  </div>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="px-2 py-0.5 rounded-full bg-indigo-50 text-[#4338CA] text-[10px] font-medium">ประชุมภายใน</span>
                    <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-600 text-[10px] font-medium">เป็นทางการ</span>
                    <span className="px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-600 text-[10px] font-medium">เชิงบวก</span>
                  </div>
                </div>

                {/* Audio bar */}
                <div className="px-5 py-2.5 border-b border-gray-50">
                  <div className="flex items-center gap-3">
                    <svg viewBox="0 0 16 16" className="w-3 h-3 text-[#B0AED0] fill-[#B0AED0] shrink-0"><polygon points="4,2 14,8 4,14" /></svg>
                    <div className="flex-1 h-1 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-[#4338CA] rounded-full" style={{ width: '28%' }} />
                    </div>
                    <span className="text-[10px] text-[#B0AED0] shrink-0 font-mono">12:35 / 45:00</span>
                  </div>
                </div>

                <div className="flex">
                  {/* Timeline content */}
                  <div className="flex-1 p-5 space-y-0.5">
                    {[
                      { name: 'นภา รัตนกุล', time: '0:01', text: 'สวัสดีค่ะ วันนี้เรามาคุยเรื่องงบประมาณไตรมาส 2 กันนะคะ', color: '#E11D48' },
                      { name: 'แดเนียล จอห์นสัน', time: '0:28', text: 'ครับ ผมเตรียมตัวเลขมาแล้ว รวมอยู่ที่ประมาณ 2.4 ล้านบาท', color: '#2563EB' },
                      { name: 'พิมพ์ใจ สุวรรณ', time: '1:05', text: 'ทางฝ่ายบัญชีดูแล้ว ตัวเลขนี้สอดคล้องกับแผนที่วางไว้ค่ะ', color: '#059669' },
                      { name: 'นภา รัตนกุล', time: '1:32', text: 'ดีค่ะ งั้นขอสรุป action items ก่อนนะคะ', color: '#E11D48' },
                      { name: 'แดเนียล จอห์นสัน', time: '2:10', text: 'ผมจะจัดทำรายงานสรุปงบประมาณให้เสร็จภายในวันศุกร์ครับ', color: '#2563EB' },
                      { name: 'พิมพ์ใจ สุวรรณ', time: '2:35', text: 'ค่ะ ทางบัญชีจะส่งรายละเอียดค่าใช้จ่ายให้ภายในสัปดาห์นี้', color: '#059669' },
                    ].map((l, i) => (
                      <div key={i} className="flex gap-3 py-2 px-2 rounded-md hover:bg-indigo-50/30 transition-colors">
                        <div className="text-[10px] text-[#B0AED0] w-8 shrink-0 pt-1 font-mono">{l.time}</div>
                        <div className="w-1 shrink-0 rounded-full" style={{ background: l.color }} />
                        <div className="min-w-0">
                          <div className="text-[10px] font-semibold mb-0.5" style={{ color: l.color }}>{l.name}</div>
                          <p className="text-[13px] text-[#5A5D8D] leading-relaxed">{l.text}</p>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Right panel */}
                  <div className="hidden md:block w-44 border-l border-gray-100 p-4 shrink-0">
                    {/* Action buttons */}
                    <div className="text-[11px] font-semibold text-[#0F0F3D] mb-2">ดำเนินการ</div>
                    <div className="space-y-1.5 mb-4">
                      {[
                        { icon: '📋', label: 'MoM' },
                        { icon: '📄', label: 'ร่างเอกสาร' },
                        { icon: '✉️', label: 'ส่งอีเมล' },
                        { icon: '✨', label: 'AI สรุป' },
                      ].map((a, i) => (
                        <div key={i} className="flex items-center gap-2 py-1.5 px-2.5 rounded-lg bg-[#F8F7FF] border border-indigo-50 hover:border-[#4338CA]/30 transition-colors cursor-pointer">
                          <span className="text-sm">{a.icon}</span>
                          <span className="text-[10px] font-medium text-[#5A5D8D]">{a.label}</span>
                        </div>
                      ))}
                    </div>

                    <div className="text-[11px] font-semibold text-[#0F0F3D] mb-3">ผู้พูด</div>
                    <div className="space-y-3">
                      {[
                        { name: 'นภา', pct: 40, color: '#E11D48' },
                        { name: 'แดเนียล', pct: 35, color: '#2563EB' },
                        { name: 'พิมพ์ใจ', pct: 25, color: '#059669' },
                      ].map((s, i) => (
                        <div key={i}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[10px] font-medium text-[#5A5D8D]">{s.name}</span>
                            <span className="text-[10px] text-[#B0AED0]">{s.pct}%</span>
                          </div>
                          <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${s.pct}%`, background: s.color }} />
                          </div>
                        </div>
                      ))}
                    </div>


                  </div>
                </div>

              </div>
            </div>
          </div>

        </div>
      </div>
    </section>
  );
}

/* ──────────────────────── Logo Marquee ──────────────────────── */

function LogoMarquee() {
  const logos = ['กระทรวงการคลัง', 'สำนักงบประมาณ', 'กรมบัญชีกลาง', 'สำนักงาน กพ.', 'ธนาคารแห่งประเทศไทย', 'กระทรวง DES', 'สำนักงาน ก.พ.ร.', 'สภาพัฒน์'];
  return (
    <section className="py-14 bg-white overflow-hidden">
      <Reveal>
        <p className="text-center text-[#0F0F3D] font-bold text-lg mb-8">
          ได้รับความไว้วางใจจาก <span className="text-[#4338CA]">องค์กรชั้นนำ</span> ทั่วประเทศ
        </p>
      </Reveal>
      <div className="relative">
        <div className="absolute left-0 top-0 bottom-0 w-32 bg-gradient-to-r from-white to-transparent z-10" />
        <div className="absolute right-0 top-0 bottom-0 w-32 bg-gradient-to-l from-white to-transparent z-10" />
        <div className="flex animate-[marquee_30s_linear_infinite]">
          {[...logos, ...logos, ...logos].map((name, i) => (
            <div key={i} className="flex-shrink-0 px-8 py-3 mx-3 text-sm font-semibold text-[#5A5D8D] border border-gray-200 rounded-lg whitespace-nowrap hover:text-[#4338CA] hover:border-indigo-300 transition-colors bg-white">
              {name}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ──────────────────────── Feature Sections (tldv: text left/right + visual, centered title) ──────────────────────── */

const FEATURES = [
  {
    title: <>ไม่ต้องจดบันทึกประชุม<br />อีกต่อไป — <span className="text-[#4338CA]">AI ทำให้คุณ</span></>,
    desc: 'AI ถอดเสียงภาษาไทยอัตโนมัติ รองรับทุกรูปแบบไฟล์เสียง ไม่ว่าจะบันทึกจากมือถือ Zoom หรือห้องประชุม — ผลลัพธ์แม่นยำ พร้อมใช้งานทันที',
    desc2: 'ปรับแต่ง format ได้ตามต้องการ ไม่ว่าจะเป็นรายงานประชุม สรุปสั้น หรือ MoM แบบทางการ',
    cta: 'ดูเพิ่มเติมเรื่องถอดเสียง',
    visual: 'transcript',
  },
  {
    title: <>รู้ว่าใครพูดอะไร — <span className="text-[#4338CA]">แยกผู้พูดอัตโนมัติ</span></>,
    desc: 'AI แยกเสียงผู้พูดแต่ละคนโดยไม่ต้องตั้งค่า รองรับ 2-10 คนในห้องประชุม พร้อม Voiceprint Learning จดจำเสียง auto-assign ครั้งถัดไป',
    desc2: 'ยิ่งใช้ยิ่งแม่น — ทุกครั้งที่อัพโหลดเสียงใหม่ AI เรียนรู้เสียงผู้พูดเพิ่มเติม ทำให้การระบุตัวตนแม่นยำขึ้นเรื่อยๆ',
    cta: 'ดูเพิ่มเติมเรื่อง Speaker',
    visual: 'speakers',
  },
  {
    title: <>สรุป <span className="text-[#4338CA]">MoM อัตโนมัติ</span> — แม่นยำ 99%</>,
    desc: 'AI สรุปประเด็นสำคัญ มติที่ประชุม Action Items ผู้รับผิดชอบ และกำหนดส่ง ครบถ้วนพร้อมใช้งานทันที',
    desc2: 'ไม่ต้องเสียเวลาเขียน MoM อีก 3 ชั่วโมงหลังประชุม — Voizely.ai ทำให้คุณใน 5 นาที ด้วยความแม่นยำ 99%',
    cta: 'ดูเพิ่มเติมเรื่อง MoM',
    visual: 'mom',
  },
  {
    title: <>ไม่ได้แค่ถอดเสียง — <span className="text-[#4338CA]">ต่อยอดได้ทันที</span></>,
    desc: 'จากผลการถอดเสียง สามารถจัดทำเอกสารทางการ ส่งอีเมลสรุปให้ผู้เข้าร่วมประชุม หรือถาม AI Chatbot เพื่อค้นหาข้อมูลจากทุกการประชุมที่ผ่านมา',
    desc2: 'ทุกอย่างเชื่อมต่อกันอัตโนมัติ — ลดเวลาทำงานซ้ำๆ ให้คุณโฟกัสกับสิ่งที่สำคัญกว่า',
    cta: 'ดูเพิ่มเติมเรื่องการดำเนินการ',
    visual: 'actions',
  },
];

function FeatureVisual({ type }) {
  if (type === 'transcript') return (
    <div className="rounded-2xl bg-white border border-gray-100 shadow-lg shadow-indigo-50/50 overflow-hidden">
      <div className="p-5">
        {[
          { c: 'indigo', name: 'ผู้พูด 1', time: '00:00:12', text: 'เริ่มประชุมครับ วาระแรกเรื่องงบประมาณ...' },
          { c: 'emerald', name: 'ผู้พูด 2', time: '00:00:34', text: 'งบประมาณไตรมาสนี้เราได้รับอนุมัติแล้ว...' },
          { c: 'purple', name: 'ผู้พูด 1', time: '00:01:02', text: 'ดีครับ งั้นเรามาดูรายละเอียดกัน...' },
        ].map((l, i) => (
          <div key={i} className={`flex gap-3 py-3 ${i > 0 ? 'border-t border-gray-50' : ''}`}>
            <div className={`w-1 rounded-full shrink-0 ${l.c === 'indigo' ? 'bg-[#4338CA]' : l.c === 'emerald' ? 'bg-emerald-500' : 'bg-purple-500'}`} />
            <div>
              <span className={`text-xs font-semibold ${l.c === 'indigo' ? 'text-[#4338CA]' : l.c === 'emerald' ? 'text-emerald-600' : 'text-purple-600'}`}>{l.name}</span>
              <span className="text-xs text-[#B0AED0] ml-2">{l.time}</span>
              <p className="text-sm text-[#5A5D8D] mt-0.5">{l.text}</p>
            </div>
          </div>
        ))}
      </div>
      {/* Integration icons row */}
      <div className="flex items-center justify-center gap-3 px-5 py-3 bg-gray-50/50 border-t border-gray-50">
        {['MP3', 'WAV', 'M4A', 'OGG', 'FLAC'].map(f => (
          <span key={f} className="px-2 py-0.5 text-[10px] font-semibold text-[#B0AED0] bg-white rounded border border-gray-100">{f}</span>
        ))}
      </div>
    </div>
  );

  if (type === 'speakers') return (
    <div className="rounded-2xl bg-white border border-gray-100 shadow-lg shadow-indigo-50/50 overflow-hidden p-5">
      {[
        { name: 'กมล วิชาญ', role: 'ประธานที่ประชุม', pct: 45, color: '#4338CA' },
        { name: 'สมชาย ใจดี', role: 'ผู้จัดการโครงการ', pct: 30, color: '#059669' },
        { name: 'นภา รัตนกุล', role: 'ฝ่ายบัญชี', pct: 25, color: '#7C3AED' },
      ].map((s, i) => (
        <div key={i} className={`flex items-center gap-3 py-3 ${i > 0 ? 'border-t border-gray-50' : ''}`}>
          <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ backgroundColor: s.color + '15' }}>
            <UserCheck className="w-5 h-5" style={{ color: s.color }} />
          </div>
          <div className="flex-1">
            <div className="flex justify-between">
              <span className="text-sm font-semibold text-[#0F0F3D]">{s.name}</span>
              <span className="text-xs text-[#B0AED0]">{s.pct}%</span>
            </div>
            <div className="text-xs text-[#B0AED0]">{s.role}</div>
            <div className="mt-1.5 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full rounded-full transition-all duration-1000" style={{ width: `${s.pct}%`, backgroundColor: s.color }} />
            </div>
          </div>
        </div>
      ))}
      <div className="mt-3 p-3 rounded-lg bg-indigo-50/50 border border-indigo-100/50">
        <div className="text-xs font-semibold text-[#4338CA]">Voiceprint Learning</div>
        <div className="text-[11px] text-[#5A5D8D] mt-0.5">จดจำเสียง auto-assign ครั้งถัดไป</div>
      </div>
    </div>
  );

  if (type === 'actions') return (
    <div className="rounded-2xl bg-white border border-gray-100 shadow-lg shadow-indigo-50/50 overflow-hidden p-5 space-y-4">
      {[
        { icon: '📄', title: 'จัดทำเอกสาร', desc: 'สร้างบันทึกข้อความ รายงานการประชุม หนังสือราชการ จาก MoM อัตโนมัติ', color: '#4338CA' },
        { icon: '✉️', title: 'ส่งอีเมลสรุป', desc: 'ส่งสรุปประชุมพร้อม Action Items ให้ผู้เข้าร่วมทุกคนในคลิกเดียว', color: '#059669' },
        { icon: '🤖', title: 'AI Chatbot', desc: 'ถามคำถามจากทุกการประชุม — "เมื่อวานใครรับผิดชอบเรื่องนี้?" AI ตอบได้ทันที', color: '#E11D48' },
      ].map((a, i) => (
        <div key={i} className="flex gap-4 p-3 rounded-xl bg-gray-50/80 border border-gray-100/50 hover:border-indigo-200 transition-colors">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center text-lg shrink-0" style={{ backgroundColor: a.color + '12' }}>
            {a.icon}
          </div>
          <div>
            <div className="text-sm font-semibold text-[#0F0F3D]">{a.title}</div>
            <div className="text-xs text-[#5A5D8D] mt-0.5 leading-relaxed">{a.desc}</div>
          </div>
        </div>
      ))}
    </div>
  );

  return (
    <div className="rounded-2xl bg-white border border-gray-100 shadow-lg shadow-indigo-50/50 overflow-hidden p-5 space-y-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-[#4338CA]">
        <BrainCircuit className="w-4 h-4" /> สรุปการประชุมอัตโนมัติ
      </div>
      {[
        { label: 'มติที่ประชุม', text: 'อนุมัติแผนงานไตรมาส 2 ด้วยมติเอกฉันท์' },
        { label: 'Action Items', text: '1. สมชาย: จัดทำรายงาน (กำหนด: ศุกร์นี้)\n2. นภา: ส่งงบประมาณ (ภายในสัปดาห์)' },
        { label: 'ติดตาม', text: 'รอผล UAT — ประชุมครั้งหน้า' },
      ].map((item, i) => (
        <div key={i} className="p-3 rounded-lg bg-gray-50 border border-gray-100/50">
          <div className="text-xs font-semibold text-[#0F0F3D] mb-0.5">{item.label}</div>
          <div className="text-sm text-[#5A5D8D] whitespace-pre-line">{item.text}</div>
        </div>
      ))}
    </div>
  );
}

function FeatureSection({ feature, reverse }) {
  return (
    <div className="py-20">
      <div className={`max-w-[1200px] mx-auto px-6 flex flex-col ${reverse ? 'lg:flex-row-reverse' : 'lg:flex-row'} items-center gap-12 lg:gap-20`}>
        <Reveal className="flex-1 max-w-[500px]" direction={reverse ? 'left' : 'right'}>
          <h2 className="text-3xl md:text-[40px] font-bold text-[#0F0F3D] leading-tight mb-5">{feature.title}</h2>
          <p className="text-[#5A5D8D] leading-relaxed mb-4">{feature.desc}</p>
          <p className="text-[#5A5D8D] leading-relaxed mb-6">{feature.desc2}</p>
          <a href="#contact" className="inline-flex items-center gap-2 px-6 py-3 text-sm font-semibold text-white bg-[#4338CA] rounded-full hover:bg-[#3730A3] hover:-translate-y-0.5 transition-all duration-300">
            {feature.cta}
            <ArrowRight className="w-4 h-4" />
          </a>
        </Reveal>
        <Reveal className="flex-1 w-full max-w-[500px]" direction={reverse ? 'right' : 'left'} delay={0.15}>
          <FeatureVisual type={feature.visual} />
        </Reveal>
      </div>
    </div>
  );
}

function Features() {
  return (
    <section id="features" className="relative">
      {/* Subtle gradient bg for alternating sections */}
      {FEATURES.map((f, i) => (
        <div key={i} className={i % 2 === 0 ? 'bg-white' : ''} style={i % 2 === 1 ? { background: 'linear-gradient(180deg, #F8F7FF 0%, #FFFFFF 100%)' } : undefined}>
          <FeatureSection feature={f} reverse={i % 2 === 1} />
        </div>
      ))}
    </section>
  );
}

/* ──────────────────────── Security / Trust ──────────────────────── */

function SecuritySection() {
  return (
    <section className="py-24 relative overflow-hidden" style={{ background: 'linear-gradient(180deg, #FCE7F3 0%, #EDE9FE 50%, #FFFFFF 100%)' }}>
      <div className="max-w-[1200px] mx-auto px-6 text-center">
        <Reveal>
          <h2 className="text-3xl md:text-[40px] font-bold text-[#0F0F3D] leading-tight mb-4">
            ข้อมูลของคุณ <span className="text-[#4338CA]">ปลอดภัยเสมอ</span>
          </h2>
          <p className="text-[#5A5D8D] max-w-2xl mx-auto mb-4">ข้อมูลถูกเข้ารหัสทั้ง transit และ at rest ด้วยมาตรฐาน AES-256</p>
          <p className="text-[#5A5D8D] max-w-2xl mx-auto mb-12">สำหรับองค์กรที่ต้องการความปลอดภัยสูงสุด สามารถเลือก On-Premise ติดตั้งในองค์กรได้</p>
        </Reveal>
        <Stagger className="flex flex-wrap items-center justify-center gap-12" gap={0.15}>
          {[
            { icon: Lock, label: 'เข้ารหัส\nAES-256' },
            { icon: Shield, label: 'On-Premise\nReady' },
            { icon: Building2, label: 'Enterprise\nGrade' },
          ].map(item => (
            <div key={item.label} className="flex flex-col items-center gap-3 group">
              <div className="w-20 h-20 rounded-2xl bg-white border border-gray-100 shadow-sm flex items-center justify-center group-hover:shadow-md group-hover:-translate-y-1 transition-all duration-300">
                <item.icon className="w-8 h-8 text-[#4338CA]" />
              </div>
              <span className="text-sm font-semibold text-[#0F0F3D] text-center whitespace-pre-line">{item.label}</span>
            </div>
          ))}
        </Stagger>
      </div>
    </section>
  );
}

/* ──────────────────────── Testimonial (tldv style: big quote centered) ──────────────────────── */

function Testimonial() {
  return (
    <section className="py-28 bg-white">
      <Reveal className="max-w-[800px] mx-auto px-6 text-center">
        <div className="text-[#B0AED0] text-sm font-semibold tracking-wider uppercase mb-6">ผู้ใช้งานจริง</div>
        <blockquote className="text-2xl md:text-[32px] font-bold text-[#0F0F3D] leading-snug mb-8">
          "เมื่อก่อนต้องนั่งจดประชุม 2 ชั่วโมง แล้วเขียน MoM อีก 3 ชั่วโมง ตอนนี้แค่ส่งไฟล์เสียงเข้า Voizely.ai ก็ได้ MoM ครบภายใน 5 นาที"
        </blockquote>
        <div className="flex items-center justify-center gap-3">
          <div className="w-12 h-12 rounded-full bg-gradient-to-br from-indigo-100 to-purple-100 flex items-center justify-center text-[#4338CA] font-bold text-sm">ผ</div>
          <div className="text-left">
            <div className="text-sm font-semibold text-[#0F0F3D]">ผู้ใช้งานจริง</div>
            <div className="text-sm text-[#B0AED0]">องค์กรภาครัฐ</div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

/* ──────────────────────── How it works ──────────────────────── */

const STEPS = [
  { icon: Headphones, title: 'อัพโหลดไฟล์เสียง', desc: 'ลากวางไฟล์เสียงจากทุกแหล่ง — มือถือ, Zoom, ห้องประชุม' },
  { icon: BrainCircuit, title: 'AI ประมวลผลทันที', desc: 'ถอดเสียง แยก speaker สรุป MoM โดยอัตโนมัติ' },
  { icon: FileText, title: 'รับ MoM พร้อมใช้', desc: 'ดาวน์โหลด transcript + MoM มติ Action Items ครบ' },
];

function HowItWorks() {
  return (
    <section id="how-it-works" className="py-24" style={{ background: 'linear-gradient(180deg, #F8F7FF 0%, #FFFFFF 100%)' }}>
      <div className="max-w-[1200px] mx-auto px-6">
        <Reveal className="text-center mb-16">
          <h2 className="text-3xl md:text-[40px] font-bold text-[#0F0F3D] mb-4">ง่ายแค่ <span className="text-[#4338CA]">3 ขั้นตอน</span></h2>
          <p className="text-[#5A5D8D]">ไม่ต้องตั้งค่า ไม่ต้องเรียนรู้ ส่งไฟล์มาแล้วรับผลลัพธ์</p>
        </Reveal>
        <Stagger className="grid md:grid-cols-3 gap-10" gap={0.15}>
          {STEPS.map((s, i) => (
            <div key={i} className="text-center group">
              <div className="relative inline-flex items-center justify-center w-24 h-24 rounded-2xl bg-white border border-gray-100 shadow-sm mb-6 group-hover:shadow-lg group-hover:shadow-indigo-100/50 group-hover:-translate-y-2 transition-all duration-500">
                <s.icon className="w-10 h-10 text-[#4338CA]" />
                <span className="absolute -top-2.5 -right-2.5 w-7 h-7 rounded-full bg-[#4338CA] text-white text-xs font-bold flex items-center justify-center">{i + 1}</span>
              </div>
              <h3 className="text-lg font-bold text-[#0F0F3D] mb-2">{s.title}</h3>
              <p className="text-sm text-[#5A5D8D] leading-relaxed max-w-xs mx-auto">{s.desc}</p>
            </div>
          ))}
        </Stagger>
      </div>
    </section>
  );
}

/* ──────────────────────── Pricing ──────────────────────── */

const PLANS = [
  {
    name: 'Standard',
    desc: 'สำหรับทีมทั่วไป',
    highlight: false,
    features: ['ถอดเสียงภาษาไทย', 'แยก Speaker อัตโนมัติ (90%+)', 'สรุป MoM + Action Items', 'รองรับไฟล์เสียงทุกรูปแบบ', 'Voiceprint Learning', 'ส่งไฟล์เสียงผ่านระบบ'],
  },
  {
    name: 'Premium',
    desc: 'สำหรับองค์กรที่ต้องการความแม่นยำสูงสุด',
    highlight: true,
    features: ['ทุกอย่างใน Standard', 'Hardware Bundle เฉพาะทาง', 'แยก Speaker แม่นยำ 99%+', 'Multi-channel Audio', 'On-Premise ติดตั้งในองค์กร', 'Priority Support'],
  },
];

function Pricing() {
  return (
    <section id="pricing" className="py-24 bg-white">
      <div className="max-w-[1200px] mx-auto px-6">
        <Reveal className="text-center mb-16">
          <h2 className="text-3xl md:text-[40px] font-bold text-[#0F0F3D] mb-4">แพ็กเกจที่ <span className="text-[#4338CA]">เหมาะกับคุณ</span></h2>
          <p className="text-[#5A5D8D]">เลือกแพ็กเกจตามความต้องการ ไม่มีค่าใช้จ่ายแอบแฝง</p>
        </Reveal>
        <Stagger className="grid md:grid-cols-2 gap-8 max-w-3xl mx-auto" gap={0.15}>
          {PLANS.map(p => (
            <div key={p.name} className={`relative rounded-2xl p-8 transition-all duration-500 hover:-translate-y-2 ${p.highlight ? 'bg-[#4338CA] text-white shadow-xl shadow-indigo-200 hover:shadow-2xl' : 'bg-white border border-gray-200 hover:shadow-lg hover:border-indigo-200'}`}>
              {p.highlight && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 bg-amber-400 text-amber-900 text-xs font-bold rounded-full">แนะนำ</span>
              )}
              <h3 className={`text-2xl font-bold mb-1 ${p.highlight ? 'text-white' : 'text-[#0F0F3D]'}`}>{p.name}</h3>
              <p className={`text-sm mb-2 ${p.highlight ? 'text-indigo-200' : 'text-[#B0AED0]'}`}>{p.desc}</p>
              <div className={`text-lg font-semibold mb-6 ${p.highlight ? 'text-white' : 'text-[#0F0F3D]'}`}>ติดต่อสอบถาม</div>
              <ul className="space-y-3 mb-8">
                {p.features.map(f => (
                  <li key={f} className="flex items-start gap-3 text-sm">
                    <Check className={`w-5 h-5 shrink-0 mt-0.5 ${p.highlight ? 'text-indigo-200' : 'text-[#4338CA]'}`} />
                    <span className={p.highlight ? 'text-white/90' : 'text-[#5A5D8D]'}>{f}</span>
                  </li>
                ))}
              </ul>
              <a href="#contact" className={`block text-center py-3 rounded-full font-semibold transition-all duration-300 hover:-translate-y-0.5 ${p.highlight ? 'bg-white text-[#4338CA] hover:bg-indigo-50' : 'bg-[#4338CA] text-white hover:bg-[#3730A3]'}`}>
                ติดต่อเรา
              </a>
            </div>
          ))}
        </Stagger>
      </div>
    </section>
  );
}

/* ──────────────────────── FAQ (tldv style) ──────────────────────── */

const FAQS = [
  { q: 'รองรับไฟล์เสียงรูปแบบใดบ้าง?', a: 'รองรับทุกรูปแบบ — MP3, WAV, M4A, OGG, FLAC และอื่นๆ ระบบจะ re-encode อัตโนมัติเพื่อคุณภาพสูงสุด' },
  { q: 'แยก Speaker ได้กี่คน?', a: 'รองรับ 2-10 คนต่อการประชุม Standard Plan แม่นยำ 90%+ และ Premium Plan ด้วย Hardware Bundle แม่นยำ 99%+' },
  { q: 'ข้อมูลเสียงปลอดภัยไหม?', a: 'ข้อมูลถูกเข้ารหัสทั้ง transit และ at rest สำหรับองค์กรที่ต้องการความปลอดภัยสูงสุด สามารถเลือก On-Premise ได้' },
  { q: 'ใช้เวลาประมวลผลนานเท่าไร?', a: 'ไฟล์เสียง 1 ชั่วโมง ประมวลผลเสร็จภายใน 5 นาที รวมถอดเสียง แยก Speaker และสรุป MoM' },
  { q: 'ทดลองใช้งานฟรีได้ไหม?', a: 'ได้ครับ ติดต่อเราเพื่อรับสิทธิ์ทดลองใช้งานฟรี ไม่มีค่าใช้จ่าย' },
];

function FAQ() {
  const [openIdx, setOpenIdx] = useState(null);
  return (
    <section id="faq" className="py-24" style={{ background: 'linear-gradient(180deg, #FFFFFF 0%, #F8F7FF 100%)' }}>
      <div className="max-w-[700px] mx-auto px-6">
        <Reveal className="text-center mb-12">
          <h2 className="text-3xl md:text-[40px] font-bold text-[#0F0F3D]">คำถามที่พบบ่อย</h2>
        </Reveal>
        <Stagger className="space-y-3" gap={0.08}>
          {FAQS.map((faq, i) => (
            <div key={i} className="border border-gray-200 rounded-xl overflow-hidden hover:border-indigo-200 transition-colors bg-white">
              <button
                onClick={() => setOpenIdx(openIdx === i ? null : i)}
                className="w-full flex items-center justify-between px-6 py-4 text-left"
              >
                <span className="text-sm font-semibold text-[#0F0F3D]">{faq.q}</span>
                <ChevronDown className={`w-4 h-4 text-[#B0AED0] shrink-0 transition-transform duration-300 ${openIdx === i ? 'rotate-180' : ''}`} />
              </button>
              <div className="overflow-hidden transition-all duration-300" style={{ maxHeight: openIdx === i ? '200px' : '0', opacity: openIdx === i ? 1 : 0 }}>
                <div className="px-6 pb-4 text-sm text-[#5A5D8D] leading-relaxed">{faq.a}</div>
              </div>
            </div>
          ))}
        </Stagger>
      </div>
    </section>
  );
}

/* ──────────────────────── CTA ──────────────────────── */

function CTA() {
  return (
    <section id="contact" className="py-24 bg-white">
      <Reveal>
        <div className="max-w-[1200px] mx-auto px-6">
          <div className="relative rounded-3xl overflow-hidden p-12 md:p-20 text-center" style={{ background: 'linear-gradient(135deg, #4338CA 0%, #3730A3 50%, #312E81 100%)' }}>
            <div className="absolute top-0 right-0 w-72 h-72 bg-white/5 rounded-full blur-3xl" />
            <div className="absolute bottom-0 left-0 w-56 h-56 bg-indigo-400/10 rounded-full blur-3xl" />
            <div className="relative">
              <h2 className="text-3xl md:text-[44px] font-bold text-white mb-4 leading-tight">พร้อมเปลี่ยนการประชุมของคุณ?</h2>
              <p className="text-indigo-200 max-w-lg mx-auto mb-10 text-lg">เริ่มต้นใช้ Voizely.ai วันนี้ — ทดลองใช้ฟรี ไม่มีค่าใช้จ่าย</p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                <a href="mailto:contact@cappa.ai" className="px-8 py-4 bg-white text-[#4338CA] font-semibold rounded-full hover:bg-indigo-50 hover:shadow-lg hover:-translate-y-1 transition-all duration-300 flex items-center gap-2">
                  <Building2 className="w-4 h-4" />
                  ติดต่อทีมขาย
                </a>
                <a href="#" className="group px-8 py-4 border-2 border-white/25 text-white font-semibold rounded-full hover:bg-white/10 hover:-translate-y-1 transition-all duration-300 flex items-center gap-2">
                  ทดลองใช้งานฟรี
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </a>
              </div>
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

/* ──────────────────────── Footer ──────────────────────── */

function Footer() {
  return (
    <footer className="py-10 bg-white border-t border-gray-100">
      <div className="max-w-[1200px] mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-6">
        <a href="#" className="flex items-center group">
          <img src="/logo.png" alt="Voizely" className="h-6 group-hover:scale-105 transition-transform" />
        </a>
        <div className="flex items-center gap-6">
          {NAV.map(l => (
            <a key={l.href} href={l.href} className="text-sm text-[#B0AED0] hover:text-[#4338CA] transition-colors">{l.label}</a>
          ))}
        </div>
        <p className="text-sm text-[#B0AED0]">&copy; 2026 Voizely.ai</p>
      </div>
    </footer>
  );
}

/* ──────────────────────── Main ──────────────────────── */

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white" style={{ fontFamily: "'Prompt', system-ui, sans-serif" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Work+Sans:wght@400;500;600;700&display=swap');
        @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-20px)} }
        @keyframes floatSlow { 0%,100%{transform:translateY(0) rotate(-3deg)} 50%{transform:translateY(-10px) rotate(-3deg)} }
        @keyframes marquee { 0%{transform:translateX(0)} 100%{transform:translateX(-33.33%)} }
        html { scroll-behavior: smooth; }
      `}</style>
      <Navbar />
      <Hero />
      <LogoMarquee />
      <Features />
      <SecuritySection />
      <Testimonial />
      <CTA />
      <Footer />
    </div>
  );
}

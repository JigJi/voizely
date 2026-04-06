/* === Upload === */
document.addEventListener('DOMContentLoaded', () => {
    const label = document.getElementById('upload-label');
    const input = document.getElementById('file-input');
    const form = document.getElementById('upload-form');

    if (label && input && form) {
        label.addEventListener('click', () => input.click());
        label.addEventListener('dragover', e => { e.preventDefault(); label.style.borderColor = '#2563eb'; });
        label.addEventListener('dragleave', () => { label.style.borderColor = '#cbd5e1'; });
        label.addEventListener('drop', e => {
            e.preventDefault();
            label.style.borderColor = '#cbd5e1';
            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                htmx.trigger(form, 'submit');
            }
        });
        input.addEventListener('change', () => {
            if (input.files.length) htmx.trigger(form, 'submit');
        });
    }

    // Audio player highlight — find closest segment
    const player = document.getElementById('audio-player');
    if (player) {
        const items = document.querySelectorAll('.tl-item');
        if (items.length) {
            player.addEventListener('timeupdate', () => {
                const t = player.currentTime;
                let bestItem = null;
                let bestDist = Infinity;

                items.forEach(item => {
                    const s = parseFloat(item.dataset.start);
                    const e = parseFloat(item.dataset.end);
                    item.classList.remove('active');

                    // Check if current time falls within this segment
                    if (t >= s - 0.2 && t < e + 1) {
                        const dist = Math.abs(t - (s + e) / 2);
                        if (dist < bestDist) {
                            bestDist = dist;
                            bestItem = item;
                        }
                    }
                });

                if (bestItem) {
                    bestItem.classList.add('active');
                }
            });
        }
    }
});

/* === Tabs === */
function showTab(name, btn) {
    document.querySelectorAll('.tab-panel').forEach(el => el.classList.add('hidden'));
    const t = document.getElementById('tab-' + name);
    if (t) t.classList.remove('hidden');
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    sessionStorage.setItem('activeTab', name);
}
// Restore tab on reload
document.addEventListener('DOMContentLoaded', () => {
    const saved = sessionStorage.getItem('activeTab');
    if (saved) {
        const btn = document.querySelector('.tab[onclick*="' + saved + '"]');
        if (btn) showTab(saved, btn);
    }
});

/* === Copy === */
function copyText() {
    // Copy from the currently visible tab panel
    const el = document.querySelector('.tab-panel:not(.hidden) .timeline');
    if (!el) return;
    navigator.clipboard.writeText(el.innerText).then(() => {
        const btn = document.querySelector('.tab-action');
        if (btn) {
            const orig = btn.innerHTML;
            btn.textContent = 'คัดลอกแล้ว!';
            setTimeout(() => { btn.innerHTML = orig; }, 2000);
        }
    });
}

/* === Audio seek === */
function seekAudio(time) {
    const p = document.getElementById('audio-player');
    if (p) { p.currentTime = time; p.play(); }
}

/* === Edit title === */
function editTitle(el, transcriptionId) {
    const svg = el.querySelector('svg');
    const old = el.textContent.trim();
    const input = document.createElement('input');
    input.type = 'text';
    input.value = old;
    input.style.cssText = 'width:100%;padding:6px 10px;border:1px solid #6366f1;border-radius:6px;background:#fff;color:#000;font-size:inherit;font-weight:inherit;';
    el.textContent = '';
    el.appendChild(input);
    input.focus();
    input.select();
    function save() {
        const val = input.value.trim();
        if (!val || val === old) { window.location.reload(); return; }
        fetch('/api/transcriptions/' + transcriptionId + '/update-title', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title: val})
        }).then(r => r.json()).then(() => window.location.reload());
    }
    input.addEventListener('keydown', e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') window.location.reload(); });
    input.addEventListener('blur', save);
}

/* === Custom Modal (replaces alert/confirm/prompt) === */
function showModal(options) {
    // options: { title, message, type: 'confirm'|'prompt'|'alert', placeholder, value, onConfirm }
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.4);z-index:9998;display:flex;align-items:center;justify-content:center;';

    const modal = document.createElement('div');
    modal.style.cssText = 'background:#fff;border-radius:12px;padding:24px;min-width:360px;max-width:480px;box-shadow:0 20px 60px rgba(0,0,0,0.3);';

    let html = `<div style="font-size:16px;font-weight:600;margin-bottom:8px;">${options.title || ''}</div>`;
    if (options.message) html += `<div style="font-size:14px;color:#666;margin-bottom:16px;">${options.message}</div>`;
    if (options.type === 'prompt') {
        html += `<input id="modal-input" type="text" value="${options.value || ''}" placeholder="${options.placeholder || ''}" style="width:100%;padding:10px 12px;border:1px solid #d1d5db;border-radius:8px;font-size:14px;margin-bottom:16px;box-sizing:border-box;">`;
    }
    html += `<div style="display:flex;gap:8px;justify-content:flex-end;">`;
    if (options.type !== 'alert') {
        html += `<button id="modal-cancel" style="padding:8px 20px;border:1px solid #d1d5db;border-radius:8px;background:#fff;font-size:14px;cursor:pointer;">ยกเลิก</button>`;
    }
    const btnColor = options.danger ? '#ef4444' : '#6366f1';
    html += `<button id="modal-ok" style="padding:8px 20px;border:none;border-radius:8px;background:${btnColor};color:#fff;font-size:14px;font-weight:500;cursor:pointer;">${options.okText || 'ตกลง'}</button>`;
    html += `</div>`;

    modal.innerHTML = html;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const input = document.getElementById('modal-input');
    if (input) { input.focus(); input.select(); }

    function close(result) {
        overlay.remove();
        if (result !== undefined && options.onConfirm) options.onConfirm(result);
    }

    document.getElementById('modal-ok').onclick = () => {
        if (options.type === 'prompt') close(input.value.trim());
        else close(true);
    };
    const cancel = document.getElementById('modal-cancel');
    if (cancel) cancel.onclick = () => close(undefined);
    overlay.onclick = (e) => { if (e.target === overlay) close(undefined); };
    if (input) input.addEventListener('keydown', e => { if (e.key === 'Enter') document.getElementById('modal-ok').click(); if (e.key === 'Escape') close(undefined); });
}

/* === Groups === */
function toggleGroup(header) {
    const section = header.closest('.group-section');
    section.classList.toggle('collapsed');
    // Save state
    const id = section.dataset.groupId;
    const collapsed = JSON.parse(localStorage.getItem('collapsed_groups') || '{}');
    collapsed[id] = section.classList.contains('collapsed');
    localStorage.setItem('collapsed_groups', JSON.stringify(collapsed));
}

function createGroup() {
    showModal({
        title: 'สร้างกลุ่มใหม่',
        type: 'prompt',
        placeholder: 'ชื่อกลุ่ม',
        okText: 'สร้าง',
        onConfirm: (name) => {
            if (!name) return;
            fetch('/api/groups', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: name})
            }).then(r => r.json()).then(() => window.location.reload());
        }
    });
}

// Restore collapsed state on load
document.addEventListener('DOMContentLoaded', () => {
    const collapsed = JSON.parse(localStorage.getItem('collapsed_groups') || '{}');
    document.querySelectorAll('.group-section').forEach(section => {
        if (collapsed[section.dataset.groupId]) {
            section.classList.add('collapsed');
        }
    });
});

// Move to group
function moveToGroup(transcriptionId, groupId) {
    fetch('/api/transcriptions/' + transcriptionId + '/assign-group', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({group_id: parseInt(groupId)})
    }).then(r => r.json()).then(data => {
        if (data.ok) {
            showNotification('ย้ายกลุ่มแล้ว', 'success');
            setTimeout(() => window.location.reload(), 1000);
        }
    });
}

// Delete transcription with custom modal
function deleteTranscription(btn, id) {
    showModal({
        title: 'ลบไฟล์',
        message: 'ต้องการลบไฟล์นี้?',
        type: 'confirm',
        okText: 'ลบ',
        danger: true,
        onConfirm: () => {
            fetch('/htmx/delete/' + id, {method: 'POST'}).then(() => window.location.reload());
        }
    });
}

/* === Apply Corrections === */
function applyCorrections(transcriptionId) {
    fetch('/api/transcriptions/' + transcriptionId + '/apply-corrections', {
        method: 'POST'
    }).then(r => r.json()).then(data => {
        showNotification(data.count > 0 ? 'แก้ไข ' + data.count + ' จุด' : 'ไม่มีคำที่ต้องแก้ไข', data.count > 0 ? 'success' : 'info');
        if (data.count > 0) setTimeout(() => window.location.reload(), 1500);
    });
}

function showNotification(msg, type) {
    const existing = document.getElementById('notify-bar');
    if (existing) existing.remove();
    const bar = document.createElement('div');
    bar.id = 'notify-bar';
    bar.textContent = msg;
    bar.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);padding:10px 24px;border-radius:8px;font-size:14px;font-weight:500;z-index:9999;transition:opacity 0.3s;' + (type === 'success' ? 'background:#22c55e;color:#fff;' : 'background:#3b82f6;color:#fff;');
    document.body.appendChild(bar);
    setTimeout(() => { bar.style.opacity = '0'; setTimeout(() => bar.remove(), 300); }, 3000);
}

/* === Scroll to active segment === */
function scrollToActive() {
    const active = document.querySelector('.tl-item.active');
    if (active) {
        active.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

/* === Edit filename === */
function editFilename(el, audioId) {
    const old = el.textContent.trim();
    const input = document.createElement('input');
    input.type = 'text';
    input.value = old;
    input.style.cssText = 'padding:2px 6px;border:1px solid #6366f1;border-radius:4px;background:#fff;color:#000;font-size:inherit;width:200px;';
    el.replaceWith(input);
    input.focus();
    input.select();
    function save() {
        const val = input.value.trim();
        if (!val || val === old) { window.location.reload(); return; }
        fetch('/api/audio/' + audioId + '/rename', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: val})
        }).then(r => r.json()).then(() => window.location.reload());
    }
    input.addEventListener('keydown', e => { if (e.key === 'Enter') save(); if (e.key === 'Escape') window.location.reload(); });
    input.addEventListener('blur', save);
}

/* === Settings toggle === */
function toggleSettings() {
    const panel = document.getElementById('settings-panel');
    if (panel) panel.classList.toggle('hidden');
}

/* === User menu toggle === */
function toggleUserMenu() {
    const menu = document.getElementById('user-menu');
    if (menu) menu.classList.toggle('hidden');
}
document.addEventListener('click', (e) => {
    const menu = document.getElementById('user-menu');
    const btn = e.target.closest('.header-btn');
    if (menu && !btn && !menu.contains(e.target)) {
        menu.classList.add('hidden');
    }
});

/* === Rename speaker (all) — inline edit on chip === */
function renameSpeaker(oldName, transcriptionId) {
    event.stopPropagation();
    const chip = event.target.closest('.tl-speaker-chip');
    if (!chip || chip.querySelector('input')) return;

    const input = document.createElement('input');
    input.type = 'text';
    input.value = oldName;
    input.className = 'inline-edit-input';

    chip.textContent = '';
    chip.appendChild(input);
    input.focus();
    input.select();

    function save() {
        const newName = input.value.trim();
        if (!newName || newName === oldName) { window.location.reload(); return; }
        fetch('/api/transcriptions/' + transcriptionId + '/rename-speaker', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({old_name: oldName, new_name: newName})
        }).then(r => r.json()).then(data => { if (data.ok) window.location.reload(); });
    }

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') save();
        if (e.key === 'Escape') window.location.reload();
    });
    input.addEventListener('blur', save);
}

/* === Change speaker (single segment) — inline edit === */
function changeSegmentSpeaker(segId, currentSpeaker) {
    event.stopPropagation();
    const nameEl = event.target.closest('.tl-speaker').querySelector('.tl-name');
    if (!nameEl || nameEl.querySelector('input')) return;

    const input = document.createElement('input');
    input.type = 'text';
    input.value = currentSpeaker;
    input.className = 'inline-edit-input';

    nameEl.textContent = '';
    nameEl.appendChild(input);
    input.focus();
    input.select();

    function save() {
        const newSpeaker = input.value.trim();
        if (!newSpeaker || newSpeaker === currentSpeaker) { window.location.reload(); return; }
        fetch('/api/transcriptions/segments/' + segId + '/speaker', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({speaker: newSpeaker})
        }).then(r => r.json()).then(data => { if (data.ok) window.location.reload(); });
    }

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') save();
        if (e.key === 'Escape') window.location.reload();
    });
    input.addEventListener('blur', save);
}

/* === Edit topic tag (inline) === */
function editTopic(el, transcriptionId) {
    const oldText = el.textContent.trim();
    const input = document.createElement('input');
    input.type = 'text';
    input.value = oldText;
    input.className = 'inline-edit-input';
    el.textContent = '';
    el.appendChild(input);
    input.focus();
    input.select();

    function save() {
        const newText = input.value.trim();
        if (!newText || newText === oldText) { window.location.reload(); return; }
        fetch('/api/transcriptions/' + transcriptionId + '/replace-text', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({find: oldText, replace: newText})
        }).then(r => r.json()).then(data => { if (data.ok) window.location.reload(); });
    }
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') save();
        if (e.key === 'Escape') window.location.reload();
    });
    input.addEventListener('blur', save);
}

/* === Find & Replace === */
function toggleFindReplace() {
    const bar = document.getElementById('find-replace-bar');
    bar.classList.toggle('hidden');
    if (!bar.classList.contains('hidden')) {
        bar.querySelector('#fr-find').focus();
    } else {
        clearHighlights();
    }
}

function doSearch() {
    const query = document.getElementById('fr-find').value;
    clearHighlights();
    if (!query) { document.getElementById('fr-count').textContent = ''; return; }

    let count = 0;
    document.querySelectorAll('.tl-text').forEach(el => {
        const text = el.textContent;
        if (text.includes(query)) {
            const parts = text.split(query);
            el.innerHTML = parts.join('<mark class="fr-highlight">' + query.replace(/</g,'&lt;') + '</mark>');
            count += parts.length - 1;
        }
    });
    document.getElementById('fr-count').textContent = count > 0 ? 'พบ ' + count + ' จุด' : 'ไม่พบ';
}

function clearHighlights() {
    document.querySelectorAll('.tl-text').forEach(el => {
        if (el.querySelector('mark')) {
            el.textContent = el.textContent;
        }
    });
}

function doReplace(transcriptionId) {
    const find = document.getElementById('fr-find').value;
    const replace = document.getElementById('fr-replace').value;
    if (!find) return;

    const btn = document.getElementById('fr-btn');
    btn.disabled = true;
    btn.textContent = '...';

    fetch('/api/transcriptions/' + transcriptionId + '/replace-text', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({find: find, replace: replace})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) {
            btn.textContent = 'แก้แล้ว ' + data.count + ' จุด';
            setTimeout(() => window.location.reload(), 1000);
        }
    });
}

/* === Markdown Table to HTML === */
function convertMdTables(md) {
    const lines = md.split('\n');
    const result = [];
    let i = 0;
    while (i < lines.length) {
        // Detect table: line with |, next line with |---
        if (lines[i].trim().startsWith('|') && i + 1 < lines.length && /^\|[\s-:|]+\|$/.test(lines[i+1].trim())) {
            // Parse header
            const headers = lines[i].split('|').filter(c => c.trim()).map(c => c.trim());
            i += 2; // skip header + separator
            // Parse rows
            const rows = [];
            while (i < lines.length && lines[i].trim().startsWith('|')) {
                const cells = lines[i].split('|').filter(c => c.trim()).map(c => c.trim());
                rows.push(cells);
                i++;
            }
            // Build HTML table
            let html = '<table class="mom-table"><thead><tr>';
            headers.forEach(h => html += '<th>' + h + '</th>');
            html += '</tr></thead><tbody>';
            rows.forEach(row => {
                html += '<tr>';
                row.forEach(c => html += '<td>' + c + '</td>');
                html += '</tr>';
            });
            html += '</tbody></table>';
            result.push(html);
        } else {
            result.push(lines[i]);
            i++;
        }
    }
    return result.join('\n');
}

/* === MoM Modal === */
document.addEventListener('DOMContentLoaded', () => {
    const mom = document.getElementById('mom-view');
    const raw = document.getElementById('mom-raw');
    if (mom && raw && typeof marked !== 'undefined') {
        marked.setOptions({ gfm: true, breaks: true });
        let text = raw.textContent.trim();
        if (text) {
            // Parse markdown manually for tables, then use marked for the rest
            text = convertMdTables(text);
            mom.innerHTML = marked.parse(text);
        } else {
            mom.innerHTML = '<p style="color:#94a3b8;">ยังไม่ได้สร้าง MoM กดปุ่มด้านบนเพื่อสร้าง</p>';
        }
    }
});

function openMomModal() {
    const modal = document.getElementById('mom-modal');
    if (modal) modal.classList.remove('hidden');
}
function closeMomModal() {
    const modal = document.getElementById('mom-modal');
    if (modal) modal.classList.add('hidden');
}

/* === MoM Edit === */
function toggleMomEdit(editing) {
    document.getElementById('mom-view').classList.toggle('hidden', editing);
    document.getElementById('mom-editor').classList.toggle('hidden', !editing);
    document.getElementById('mom-edit-footer').classList.toggle('hidden', !editing);
    document.getElementById('mom-edit-btn').classList.toggle('hidden', editing);
}

function saveMom(transcriptionId) {
    const text = document.getElementById('mom-editor').value;
    // Save full content including metadata
    fetch('/api/transcriptions/' + transcriptionId + '/save-mom-full', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({content: text})
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) window.location.reload();
    });
}

/* === Regenerate MoM === */
let _regenTranscriptionId = null;

function regenerateMom(transcriptionId) {
    _regenTranscriptionId = transcriptionId;
    document.getElementById('confirm-modal').classList.remove('hidden');
}

function closeConfirmModal() {
    document.getElementById('confirm-modal').classList.add('hidden');
}

function confirmRegenMom() {
    closeConfirmModal();
    const btn = document.getElementById('regen-mom-btn');
    const origText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<div class="spinner-sm"></div> กำลังสร้าง...';

    fetch('/api/transcriptions/' + _regenTranscriptionId + '/regenerate-mom', {
        method: 'POST',
    })
    .then(r => r.json())
    .then(data => {
        if (data.ok) window.location.reload();
        else { btn.innerHTML = origText; btn.disabled = false; }
    })
    .catch(() => { btn.innerHTML = origText; btn.disabled = false; });
}

import { getToken, logout } from './lib/auth';

const BASE = '';

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...options.headers },
    ...options,
  });
  if (res.status === 401) { logout(); return; }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// Groups
export const getGroups = () => request('/api/groups');
export const createGroup = (name, custom_instructions) => request('/api/groups', { method: 'POST', body: JSON.stringify({ name, custom_instructions }) });
export const updateGroup = (id, data) => request(`/api/groups/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteGroup = (id) => request(`/api/groups/${id}`, { method: 'DELETE' });

// Transcriptions
export const getTranscriptions = () => request('/api/transcriptions');
export const getTranscription = (id) => request(`/api/transcriptions/${id}`);
export const getProgress = (id) => request(`/api/transcriptions/${id}/progress`);
export const deleteTranscription = (id) => request(`/api/transcriptions/${id}`, { method: 'DELETE' });
export const renameSpeaker = (id, old_name, new_name) => request(`/api/transcriptions/${id}/rename-speaker`, { method: 'POST', body: JSON.stringify({ old_name, new_name }) });
export const replaceText = (id, find, replace) => request(`/api/transcriptions/${id}/replace-text`, { method: 'POST', body: JSON.stringify({ find, replace }) });
export const applyCorrections = (id) => request(`/api/transcriptions/${id}/apply-corrections`, { method: 'POST' });
export const regenerateMom = (id) => request(`/api/transcriptions/${id}/regenerate-mom`, { method: 'POST' });
export const saveMomFull = (id, content) => request(`/api/transcriptions/${id}/save-mom-full`, { method: 'POST', body: JSON.stringify({ content }) });
export const updateTitle = (id, title) => request(`/api/transcriptions/${id}/update-title`, { method: 'POST', body: JSON.stringify({ title }) });
export const assignGroup = (id, group_id) => request(`/api/transcriptions/${id}/assign-group`, { method: 'POST', body: JSON.stringify({ group_id }) });
export const exportDocxUrl = (id) => `/api/transcriptions/${id}/export-docx`;

// Audio
export const uploadAudio = async (file) => {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch('/api/audio/upload', { method: 'POST', body: form, headers: authHeaders() });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
};
export const startTranscription = async (audioId, data) => {
  const form = new FormData();
  Object.entries(data).forEach(([k, v]) => form.append(k, v));
  const res = await fetch(`/api/audio/${audioId}/start`, { method: 'POST', body: form, headers: authHeaders() });
  return res;
};
export const renameAudio = (id, name) => request(`/api/audio/${id}/rename`, { method: 'POST', body: JSON.stringify({ name }) });
export const audioStreamUrl = (id) => `/api/audio/${id}/stream`;

// Speakers (Profile)
export const getSpeakers = () => request('/api/speakers');
export const createSpeaker = (data) => request('/api/speakers', { method: 'POST', body: JSON.stringify(data) });
export const updateSpeaker = (id, data) => request(`/api/speakers/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteSpeaker = (id) => request(`/api/speakers/${id}`, { method: 'DELETE' });

// Legacy voiceprint endpoints (backward compat)
export const getVoiceprints = () => request('/api/voiceprints');
export const updateVoiceprint = (name, data) => request(`/api/voiceprints/${encodeURIComponent(name)}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteVoiceprint = (name) => request(`/api/voiceprints/${encodeURIComponent(name)}`, { method: 'DELETE' });

// Meetings
export const getMeetings = () => request('/api/meetings');
export const processMeeting = (id, groupId, modelSize) => request(`/api/meetings/${id}/process`, { method: 'POST', body: JSON.stringify({ group_id: groupId, model_size: modelSize }) });
export const retranscribeMeeting = (id, groupId, modelSize) => request(`/api/meetings/${id}/retranscribe`, { method: 'POST', body: JSON.stringify({ group_id: groupId, model_size: modelSize }) });
export const retryMeeting = (id) => request(`/api/meetings/${id}/retry`, { method: 'POST' });
export const skipMeeting = (id) => request(`/api/meetings/${id}/skip`, { method: 'POST' });

// Corrections
export const getCorrections = () => request('/api/corrections');
export const addCorrection = (wrong, correct) => request('/api/corrections', { method: 'POST', body: JSON.stringify({ wrong, correct }) });
export const updateCorrection = (id, data) => request(`/api/corrections/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const deleteCorrection = (id) => request(`/api/corrections/${id}`, { method: 'DELETE' });

import { Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import AuthGuard from './components/AuthGuard';
import TranscriptionPage from './pages/TranscriptionPage';
import AudioConfigPage from './pages/AudioConfigPage';
import SpeakerPage from './pages/SpeakerPage';
import CorrectionPage from './pages/CorrectionPage';
import MeetingPage from './pages/MeetingPage';
import GroupSettingsPage from './pages/GroupSettingsPage';
import UploadPage from './pages/UploadPage';
import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import NotificationContainer from './components/Notification';

export default function App() {
  return (
    <>
      <NotificationContainer />
      <Routes>
        <Route path="/home" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route element={<AuthGuard><Layout /></AuthGuard>}>
          <Route path="/" element={<Navigate to="/transcriptions" replace />} />
          <Route path="/transcriptions/:id" element={<TranscriptionPage />} />
          <Route path="/transcriptions" element={<div className="flex items-center justify-center h-full text-[#9ca3af]">เลือกไฟล์จาก sidebar หรืออัพโหลดไฟล์ใหม่</div>} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/audio/:audioId/config" element={<AudioConfigPage />} />
          <Route path="/speakers" element={<SpeakerPage />} />
          <Route path="/corrections" element={<CorrectionPage />} />
          <Route path="/meetings" element={<MeetingPage />} />
          <Route path="/groups/:groupId" element={<GroupSettingsPage />} />
        </Route>
      </Routes>
    </>
  );
}

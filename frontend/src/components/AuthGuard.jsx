import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { isLoggedIn } from '../lib/auth';

export default function AuthGuard({ children }) {
  const [ok, setOk] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoggedIn()) {
      navigate('/login', { replace: true });
    } else {
      setOk(true);
    }
  }, [navigate]);

  if (!ok) return null;
  return children;
}

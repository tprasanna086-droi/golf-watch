import { useEffect } from 'react';
import './Toast.css';

const AUTO_DISMISS_MS = 4000;

export default function Toast({ message, type = 'success', onDismiss }) {
  useEffect(() => {
    const timer = window.setTimeout(() => {
      onDismiss?.();
    }, AUTO_DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [message, onDismiss]);

  if (!message) return null;

  return (
    <div
      className={`toast toast--${type}`}
      role="status"
      aria-live="polite"
    >
      {message}
    </div>
  );
}

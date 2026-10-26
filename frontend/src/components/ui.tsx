import { X } from 'lucide-react';
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';

import type { LectureStatus } from '../api/types';
import { initials, STATUS_LABELS } from '../lib/format';

export function Spinner({ size = 18 }: { size?: number }) {
  return <span className="spinner" style={{ width: size, height: size }} />;
}

export function Skeleton({ height = 16, width = '100%' }: { height?: number; width?: number | string }) {
  return <div className="skeleton" style={{ height, width }} />;
}

export function Empty({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function Avatar({
  user,
  size = 36,
}: {
  user: { first_name: string; last_name: string; avatar_url: string | null };
  size?: number;
}) {
  return (
    <span className="avatar" style={{ width: size, height: size, fontSize: size * 0.36 }}>
      {user.avatar_url ? <img src={user.avatar_url} alt="" /> : initials(user)}
    </span>
  );
}

export function Bar({ value, brand }: { value: number; brand?: boolean }) {
  return (
    <div className={`bar${brand ? ' bar-brand' : ''}`}>
      <div style={{ width: `${Math.round(Math.min(Math.max(value, 0), 1) * 100)}%` }} />
    </div>
  );
}

export function StatusBadge({ status }: { status: LectureStatus }) {
  if (status === 'ready') {
    return (
      <span className="badge badge-success">
        <span className="dot" />
        {STATUS_LABELS[status]}
      </span>
    );
  }

  if (status === 'failed') {
    return <span className="badge badge-danger">{STATUS_LABELS[status]}</span>;
  }

  return (
    <span className="badge badge-warning">
      <span className="dot dot-pulse" />
      {STATUS_LABELS[status]}
    </span>
  );
}

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal" role="dialog" aria-label={title} onMouseDown={(e) => e.stopPropagation()}>
        <div className="card-head">
          <h2>{title}</h2>
          <button className="btn btn-ghost btn-sm btn-icon" onClick={onClose} aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

/* ---------- toasts ---------- */

type Toast = { id: number; message: string; error?: boolean };
type Notify = (message: string, options?: { error?: boolean }) => void;

const ToastContext = createContext<Notify>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const notify = useCallback<Notify>((message, options) => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, message, error: options?.error }]);
    setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), 3500);
  }, []);

  return (
    <ToastContext value={notify}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast${toast.error ? ' toast-error' : ''}`}>
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext>
  );
}

export const useToast = () => useContext(ToastContext);

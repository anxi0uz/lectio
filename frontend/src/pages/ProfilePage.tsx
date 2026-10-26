import { Camera, LogOut, Trash2 } from 'lucide-react';
import { type FormEvent, useState } from 'react';
import { useNavigate } from 'react-router';

import { api } from '../api/client';
import type { User } from '../api/types';
import { useAuth } from '../auth/AuthProvider';
import { Avatar, useToast } from '../components/ui';
import { relativeDate } from '../lib/format';

export function ProfilePage() {
  const { user, setUser, logout } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [firstName, setFirstName] = useState(user?.first_name ?? '');
  const [lastName, setLastName] = useState(user?.last_name ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user) return null;

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError(null);

    try {
      setUser(await api<User>('/users/me', { method: 'PATCH', body: { first_name: firstName, last_name: lastName } }));
      toast('Профиль сохранён');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const uploadAvatar = async (file: File) => {
    const form = new FormData();
    form.append('file', file);

    try {
      const updated = await api<User>('/users/me/avatar', { method: 'PUT', body: form });
      // The URL does not change between uploads; bust the browser cache.
      setUser({ ...updated, avatar_url: `${updated.avatar_url}?v=${Date.now()}` });
      toast('Аватар обновлён');
    } catch (e) {
      toast((e as Error).message, { error: true });
    }
  };

  const removeAvatar = async () => {
    await api('/users/me/avatar', { method: 'DELETE' });
    setUser({ ...user, avatar_url: null });
  };

  const logoutEverywhere = async () => {
    await api('/auth/logout-all', { method: 'POST' }).catch(() => undefined);
    await logout();
    navigate('/');
  };

  return (
    <div className="page">
      <section className="card page-header">
        <div>
          <div className="eyebrow">Настройки</div>
          <h1>Профиль</h1>
        </div>
      </section>

      <section className="card card-pad" style={{ maxWidth: 680 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginBottom: 24 }}>
          <Avatar user={user} size={72} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div>
              <b>{user.email}</b>
              <div className="muted" style={{ fontSize: 13 }}>
                {user.role === 'teacher' ? 'Преподаватель' : 'Студент'} · с нами с {relativeDate(user.created_at)}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <label className="btn btn-sm">
                <Camera size={14} /> Сменить фото
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  hidden
                  onChange={(e) => e.target.files?.[0] && uploadAvatar(e.target.files[0])}
                />
              </label>
              {user.avatar_url && (
                <button className="btn btn-sm btn-ghost" onClick={removeAvatar}>
                  <Trash2 size={14} /> Удалить
                </button>
              )}
            </div>
          </div>
        </div>

        <form className="form" onSubmit={save}>
          {error && <div className="alert alert-error">{error}</div>}
          <div className="form-row">
            <div className="field">
              <label htmlFor="first">Имя</label>
              <input id="first" className="input" value={firstName} onChange={(e) => setFirstName(e.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="last">Фамилия</label>
              <input id="last" className="input" value={lastName} onChange={(e) => setLastName(e.target.value)} required />
            </div>
          </div>
          <button className="btn btn-primary" disabled={saving} style={{ alignSelf: 'flex-start' }}>
            Сохранить
          </button>
        </form>
      </section>

      <section className="card card-pad" style={{ maxWidth: 680 }}>
        <h2>Сеансы</h2>
        <p className="muted" style={{ margin: '6px 0 16px', fontSize: 14 }}>
          Выход на всех устройствах завершит все сеансы, кроме того, где вы войдёте снова.
        </p>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            className="btn"
            onClick={async () => {
              await logout();
              navigate('/');
            }}
          >
            <LogOut size={15} /> Выйти
          </button>
          <button className="btn btn-danger" onClick={logoutEverywhere}>
            Выйти на всех устройствах
          </button>
        </div>
      </section>
    </div>
  );
}

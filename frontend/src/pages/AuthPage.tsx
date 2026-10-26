import { BookOpen, GraduationCap, ListTree, MessageSquareText, Search } from 'lucide-react';
import { type FormEvent, useState } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router';

import type { UserRole } from '../api/types';
import { useAuth } from '../auth/AuthProvider';
import { BrandMark } from '../components/Layout';

const FEATURES = [
  { icon: <Search size={17} />, text: 'Поиск по смыслу: находит момент, даже если говорили другими словами' },
  { icon: <ListTree size={17} />, text: 'Конспект и оглавление с переходом к разделу в один клик' },
  { icon: <MessageSquareText size={17} />, text: 'AI-помощник отвечает по лекции со ссылками на таймкоды' },
];

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { user, ready, login, register } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = params.get('next') || '/';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [role, setRole] = useState<UserRole>('student');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (ready && user) return <Navigate to={next} replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setPending(true);
    setError(null);

    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register({ email, password, first_name: firstName, last_name: lastName, role });
      }
      navigate(next, { replace: true });
    } catch (e) {
      const status = (e as { status?: number }).status;
      setError(
        status === 401
          ? 'Неверный email или пароль'
          : status === 409
            ? 'Этот email уже зарегистрирован'
            : (e as Error).message,
      );
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="auth">
      <aside className="auth-side">
        <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <BrandMark />
          <b style={{ fontSize: 20 }}>Lectio</b>
        </Link>
        <div>
          <h1>Лекции, в которых легко найти нужное</h1>
          <p>Загрузите видео — получите расшифровку, конспект и помощника, который знает лекцию наизусть.</p>
        </div>
        <div className="auth-features">
          {FEATURES.map((feature) => (
            <div key={feature.text} className="auth-feature">
              <span>{feature.icon}</span>
              {feature.text}
            </div>
          ))}
        </div>
      </aside>

      <main className="auth-main">
        <div className="auth-card">
          <h1 style={{ fontSize: 26 }}>{mode === 'login' ? 'С возвращением' : 'Создать аккаунт'}</h1>
          <p className="muted" style={{ margin: '8px 0 24px' }}>
            {mode === 'login' ? 'Войдите, чтобы продолжить с того же места.' : 'Прогресс, заметки и избранное — в одном месте.'}
          </p>

          <form className="form" onSubmit={submit}>
            {error && <div className="alert alert-error">{error}</div>}

            {mode === 'register' && (
              <>
                <div className="role-picker">
                  <button
                    type="button"
                    className={`role-option${role === 'student' ? ' active' : ''}`}
                    onClick={() => setRole('student')}
                  >
                    <strong>
                      <GraduationCap size={16} /> Студент
                    </strong>
                    <span>Смотрю и учусь</span>
                  </button>
                  <button
                    type="button"
                    className={`role-option${role === 'teacher' ? ' active' : ''}`}
                    onClick={() => setRole('teacher')}
                  >
                    <strong>
                      <BookOpen size={16} /> Преподаватель
                    </strong>
                    <span>Загружаю лекции</span>
                  </button>
                </div>
                <div className="form-row">
                  <div className="field">
                    <label htmlFor="first">Имя</label>
                    <input id="first" className="input" required value={firstName} onChange={(e) => setFirstName(e.target.value)} />
                  </div>
                  <div className="field">
                    <label htmlFor="last">Фамилия</label>
                    <input id="last" className="input" required value={lastName} onChange={(e) => setLastName(e.target.value)} />
                  </div>
                </div>
              </>
            )}

            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                type="email"
                className="input"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="password">Пароль</label>
              <input
                id="password"
                type="password"
                className="input"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                minLength={mode === 'register' ? 8 : 1}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              {mode === 'register' && <span className="muted" style={{ fontSize: 12 }}>Не короче 8 символов</span>}
            </div>

            <button className="btn btn-primary" disabled={pending} style={{ height: 44 }}>
              {pending ? 'Секунду…' : mode === 'login' ? 'Войти' : 'Зарегистрироваться'}
            </button>
          </form>

          <p className="muted" style={{ marginTop: 20, fontSize: 14, textAlign: 'center' }}>
            {mode === 'login' ? (
              <>
                Впервые здесь? <Link to={`/register?next=${encodeURIComponent(next)}`} style={{ color: 'var(--brand)', fontWeight: 600 }}>Создать аккаунт</Link>
              </>
            ) : (
              <>
                Уже есть аккаунт? <Link to={`/login?next=${encodeURIComponent(next)}`} style={{ color: 'var(--brand)', fontWeight: 600 }}>Войти</Link>
              </>
            )}
          </p>
        </div>
      </main>
    </div>
  );
}

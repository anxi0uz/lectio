import {
  BookMarked,
  Compass,
  Heart,
  House,
  Library,
  LogIn,
  LogOut,
  Search,
  Settings,
  Sparkles,
  Upload,
} from 'lucide-react';
import { type FormEvent, useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router';

import { useAuth } from '../auth/AuthProvider';
import { fullName } from '../lib/format';
import { Avatar } from './ui';

export function BrandMark({ size = 40 }: { size?: number }) {
  return (
    <span className="brand-mark" style={{ width: size, height: size }}>
      <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 24 24" fill="none">
        <path
          d="M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}

function NavItem({ to, icon, label, end }: { to: string; icon: React.ReactNode; label: string; end?: boolean }) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
      {icon}
      {label}
    </NavLink>
  );
}

function Sidebar() {
  const { user, isTeacher, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <aside className="sidebar">
      <Link to="/" className="brand">
        <BrandMark />
        <div>
          <div className="brand-name">Lectio</div>
          <div className="brand-caption">Умные видеолекции</div>
        </div>
      </Link>

      <nav className="nav">
        <div className="nav-title">Обучение</div>
        <NavItem to="/" end icon={<House size={18} />} label="Главная" />
        <NavItem to="/courses" icon={<Library size={18} />} label="Курсы" />
        <NavItem to="/lectures" icon={<Compass size={18} />} label="Все лекции" />
        <NavItem to="/search" icon={<Search size={18} />} label="Умный поиск" />
      </nav>

      {user && (
        <nav className="nav">
          <div className="nav-title">Моё</div>
          <NavItem to="/favorites" icon={<Heart size={18} />} label="Избранное" />
          <NavItem to="/bookmarks" icon={<BookMarked size={18} />} label="Заметки" />
          {isTeacher && <NavItem to="/upload" icon={<Upload size={18} />} label="Загрузить лекцию" />}
          <NavItem to="/profile" icon={<Settings size={18} />} label="Профиль" />
        </nav>
      )}

      <div className="sidebar-footer">
        {user ? (
          <div className="user-card">
            <Avatar user={user} />
            <Link to="/profile" style={{ minWidth: 0, flex: 1 }}>
              <div className="user-card-name">{fullName(user)}</div>
              <div className="user-card-meta">{user.role === 'teacher' ? 'Преподаватель' : 'Студент'}</div>
            </Link>
            <button
              className="btn btn-ghost btn-sm btn-icon"
              title="Выйти"
              aria-label="Выйти"
              onClick={async () => {
                await logout();
                navigate('/');
              }}
            >
              <LogOut size={16} />
            </button>
          </div>
        ) : (
          <div className="card" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <Sparkles size={18} className="muted" />
            <div style={{ fontWeight: 600, fontSize: 14 }}>Сохраняйте прогресс</div>
            <p className="muted" style={{ fontSize: 13 }}>
              Закладки, избранное и история — после входа.
            </p>
            <Link to="/login" className="btn btn-primary btn-sm">
              <LogIn size={15} /> Войти
            </Link>
          </div>
        )}
      </div>
    </aside>
  );
}

function Topbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [query, setQuery] = useState('');
  const input = useRef<HTMLInputElement>(null);

  // Mirror the query of the search page so the field never lies.
  useEffect(() => {
    if (location.pathname === '/search') setQuery(params.get('q') ?? '');
  }, [location.pathname, params]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (query.trim()) navigate(`/search?q=${encodeURIComponent(query.trim())}`);
  };

  return (
    <header className="topbar">
      <form className="topbar-search" onSubmit={submit} role="search">
        <Search size={17} />
        <input
          ref={input}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Найти момент в лекциях: «как доказать теорему Пифагора»"
          aria-label="Поиск по лекциям"
        />
        <span className="kbd">Ctrl K</span>
      </form>
    </header>
  );
}

export function Layout() {
  const location = useLocation();

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  return (
    <div className="shell">
      <Sidebar />
      <main className="main">
        <Topbar />
        <Outlet />
      </main>
    </div>
  );
}

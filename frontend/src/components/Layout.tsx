import { LogOut, Search } from 'lucide-react';
import { type FormEvent, useEffect, useRef, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from 'react-router';

import { useAuth } from '../auth/AuthProvider';
import { Avatar } from './ui';

export function Logo() {
  return (
    <span className="logo">
      lectio<span>.</span>
    </span>
  );
}

function NavItem({ to, label, end }: { to: string; label: string; end?: boolean }) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
      {label}
    </NavLink>
  );
}

function HeaderSearch() {
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const [query, setQuery] = useState('');
  const input = useRef<HTMLInputElement>(null);

  // Mirror the search page's query so the field never lies.
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
    <form className="header-search" onSubmit={submit} role="search">
      <Search size={18} />
      <input
        ref={input}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Спросите, что нужно найти"
        aria-label="Поиск по лекциям"
      />
      <span className="kbd">CTRL K</span>
    </form>
  );
}

function Header() {
  const { user, isTeacher, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="header">
      <div className="header-inner">
        <Link to="/" aria-label="Lectio — на главную">
          <Logo />
        </Link>

        <nav className="nav" aria-label="Разделы">
          <NavItem to="/" end label="Главная" />
          <NavItem to="/courses" label="Курсы" />
          <NavItem to="/lectures" label="Лекции" />
          <NavItem to="/glossary" label="Термины" />
          {user && <NavItem to="/bookmarks" label="Мои заметки" />}
          {user && <NavItem to="/favorites" label="Избранное" />}
          {user && <NavItem to="/leaderboard" label="Рейтинг" />}
          {isTeacher && <NavItem to="/upload" label="Загрузить" />}
        </nav>

        <HeaderSearch />

        {user ? (
          <div className="header-user">
            <Link to="/profile" title="Профиль" aria-label="Профиль">
              <Avatar user={user} size={38} />
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
              <LogOut size={17} />
            </button>
          </div>
        ) : (
          <Link to="/login" className="btn btn-primary btn-sm">
            Войти
          </Link>
        )}
      </div>
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
      <Header />
      <main className="main">
        <Outlet />
      </main>
      <footer className="footer">
        <div className="footer-inner">
          <span>LECTIO — СМЫСЛОВОЙ ПОИСК ПО ВИДЕОЛЕКЦИЯМ</span>
          <span>КИБЕРРЫВОК 2026</span>
        </div>
      </footer>
    </div>
  );
}

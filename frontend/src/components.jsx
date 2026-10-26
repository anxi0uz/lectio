import React, { useEffect, useRef, useState } from 'react';
import {
  X,
  CircleNotch,
  MagnifyingGlass,
  ArrowUpRight,
  UploadSimple,
  LinkSimple,
  Plus,
  UserCircle,
  WarningCircle,
  CheckCircle,
} from '@phosphor-icons/react';
import { api, setAccessToken, time } from './lib/api';
import { demoSegments, demoLectures } from './lib/demo';

export function ErrorNotice({ error }) {
  return error ? (
    <div className="error-notice" role="alert">
      <WarningCircle size={19} />
      <span>
        {error.message || error}
        {error.requestId && <small>Код запроса: {error.requestId}</small>}
      </span>
    </div>
  ) : null;
}
export function Empty({
  icon: Icon = MagnifyingGlass,
  title,
  children,
  action,
}) {
  return (
    <div className="empty">
      <Icon size={36} weight="light" />
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Spinner() {
  return <CircleNotch className="spin" size={20} />;
}

export function Modal({ title, subtitle, children, onClose, wide = false }) {
  const ref = useRef();
  useEffect(() => {
    const previous = document.activeElement;
    const bodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    (
      ref.current?.querySelector('input, textarea, select') ||
      ref.current?.querySelector('button')
    )?.focus();
    function onKey(e) {
      if (e.key === 'Escape') onClose();
      if (e.key === 'Tab') {
        const elements = [
          ...ref.current.querySelectorAll(
            'button, input, select, textarea, a[href]',
          ),
        ].filter((el) => !el.disabled && el.offsetParent !== null);
        const first = elements[0],
          last = elements.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        }
        if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    }
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = bodyOverflow;
      document.removeEventListener('keydown', onKey);
      previous?.focus();
    };
  }, []);
  return (
    <div
      className="modal-backdrop"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <section
        ref={ref}
        className={`modal ${wide ? 'modal-wide' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header>
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button
            className="icon-button"
            onClick={onClose}
            aria-label="Закрыть"
          >
            <X size={21} />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}

export function AuthModal({ onClose, onSuccess }) {
  const [register, setRegister] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(null);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const values = Object.fromEntries(new FormData(e.currentTarget));
    try {
      const result = await api(`/auth/${register ? 'register' : 'login'}`, {
        method: 'POST',
        body: values,
      });
      setAccessToken(result.access_token);
      onSuccess(result.user);
      onClose();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={register ? 'Начнём учиться вместе' : 'С возвращением'}
      subtitle="Ваши лекции, заметки и прогресс — в одном месте."
      onClose={onClose}
    >
      <form onSubmit={submit} className="form">
        <ErrorNotice error={error} />
        {register && (
          <div className="form-row">
            <label>
              Имя
              <input
                name="first_name"
                required
                maxLength={100}
                autoComplete="given-name"
              />
            </label>
            <label>
              Фамилия
              <input
                name="last_name"
                required
                maxLength={100}
                autoComplete="family-name"
              />
            </label>
          </div>
        )}
        <label>
          Email
          <input
            name="email"
            type="email"
            placeholder="you@example.com"
            required
            autoComplete="email"
          />
        </label>
        <label>
          Пароль
          <input
            name="password"
            type="password"
            minLength={register ? 8 : 1}
            maxLength={128}
            required
            autoComplete={register ? 'new-password' : 'current-password'}
          />
        </label>
        {register && (
          <label>
            Я хочу
            <select name="role">
              <option value="student">Учиться — студент</option>
              <option value="teacher">Делиться знаниями — преподаватель</option>
            </select>
          </label>
        )}
        <button className="button primary full" disabled={busy}>
          {busy ? <Spinner /> : null}
          {register ? 'Создать аккаунт' : 'Войти'}
        </button>
      </form>
      <p className="form-footer">
        {register ? 'Уже есть аккаунт?' : 'Впервые в Lectio?'}{' '}
        <button
          className="text-button"
          onClick={() => {
            setRegister(!register);
            setError(null);
          }}
        >
          {register ? 'Войти' : 'Зарегистрироваться'}
        </button>
      </p>
    </Modal>
  );
}

export function SearchModal({
  onClose,
  lecture,
  demo,
  course,
  onOpen,
  initialQuery = '',
}) {
  const [query, setQuery] = useState(initialQuery),
    [scope, setScope] = useState(initialQuery ? 'all' : 'lecture'),
    [results, setResults] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(null);
  const abort = useRef();
  useEffect(() => () => abort.current?.abort(), []);
  async function search(e) {
    e.preventDefault();
    if (!query.trim()) return;
    abort.current?.abort();
    abort.current = new AbortController();
    setBusy(true);
    setError(null);
    setResults(null);
    try {
      if (demo && scope === 'lecture')
        setResults(
          demoSegments
            .filter((s) => s.text.toLowerCase().includes(query.toLowerCase()))
            .map((s) => ({
              ...s,
              chunk_id: s.id,
              lecture_id: lecture.id,
              lecture_title: lecture.title,
            })),
        );
      else {
        const params = new URLSearchParams({ q: query.trim() });
        if (scope === 'lecture' && !demo) params.set('lecture_id', lecture.id);
        if (scope === 'course' && course?.id && !demo)
          params.set('course_id', course.id);
        setResults(
          await api(`/search?${params}`, { signal: abort.current.signal }),
        );
      }
    } catch (err) {
      if (err.name !== 'AbortError') setError(err);
    } finally {
      if (!abort.current?.signal.aborted) setBusy(false);
    }
  }
  return (
    <Modal
      title="Найдите нужный момент"
      subtitle="Ищите по смыслу — даже если не помните точные слова."
      onClose={onClose}
      wide
    >
      <form className="search-form" onSubmit={search}>
        <div className="search-input">
          <MagnifyingGlass size={21} />
          <input
            autoFocus
            placeholder="Например, как проверить гипотезу?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            maxLength={500}
            required
          />
          <button className="button primary" disabled={busy}>
            {busy ? <Spinner /> : 'Найти'}
          </button>
        </div>
        <div className="scope-row">
          Искать в{' '}
          <select value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="lecture">
              Текущей лекции{demo ? ' (демо)' : ''}
            </option>
            {course && !demo && <option value="course">Курсе</option>}
            <option value="all">Всех материалах сервера</option>
          </select>
        </div>
      </form>
      <ErrorNotice error={error} />
      <div className="search-results">
        {results === null && !busy && !error && (
          <Empty title="Ответ ближе, чем кажется">
            Результаты приведут сразу к нужному фрагменту лекции.
          </Empty>
        )}
        {results?.length === 0 && (
          <Empty title="Ничего не нашлось">
            Попробуйте более общий запрос или другую область поиска.
          </Empty>
        )}
        {results?.map((hit, i) => (
          <button
            key={hit.chunk_id || i}
            className="search-result"
            onClick={() => {
              onOpen(hit.lecture_id, hit.start_seconds);
              onClose();
            }}
          >
            <div>
              <span className="timecode">{time(hit.start_seconds)}</span>
              <strong>{hit.lecture_title}</strong>
              <ArrowUpRight size={18} />
            </div>
            <p>{hit.text}</p>
          </button>
        ))}
      </div>
    </Modal>
  );
}

export function UploadModal({ courses, onClose, onCreated }) {
  const [tab, setTab] = useState('link'),
    [file, setFile] = useState(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(null);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const form = new FormData(e.currentTarget);
    try {
      let result;
      if (tab === 'course')
        result = await api('/courses', {
          method: 'POST',
          body: {
            title: form.get('title'),
            description: form.get('description') || null,
          },
        });
      else if (tab === 'link')
        result = await api('/lectures/import', {
          method: 'POST',
          body: {
            url: form.get('url'),
            ...(form.get('title') ? { title: form.get('title') } : {}),
            ...(form.get('course_id')
              ? { course_id: form.get('course_id') }
              : {}),
          },
        });
      else {
        if (!file) throw new Error('Выберите файл.');
        if (file.size > 4096 * 1024 * 1024)
          throw new Error('Файл больше 4 ГБ. Выберите файл меньшего размера.');
        form.set('file', file);
        if (!form.get('course_id')) form.delete('course_id');
        if (!form.get('title')) form.delete('title');
        result = await api('/lectures', { method: 'POST', body: form });
      }
      onCreated(result, tab === 'course');
      onClose();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title="Добавить материал"
      subtitle="Lectio подготовит расшифровку, поиск и конспект."
      onClose={onClose}
    >
      <div className="segmented">
        {[
          ['link', LinkSimple, 'По ссылке'],
          ['file', UploadSimple, 'Файл'],
          ['course', Plus, 'Новый курс'],
        ].map(([id, Icon, name]) => (
          <button
            key={id}
            className={tab === id ? 'active' : ''}
            onClick={() => {
              setTab(id);
              setError(null);
            }}
          >
            <Icon size={17} />
            {name}
          </button>
        ))}
      </div>
      <form className="form" onSubmit={submit}>
        <ErrorNotice error={error} />
        {tab === 'link' && (
          <label>
            Ссылка на видео
            <input
              name="url"
              required
              type="url"
              placeholder="https://youtube.com/watch?v=…"
            />
          </label>
        )}
        {tab === 'file' && (
          <label className="file-drop">
            <UploadSimple size={30} />
            <strong>{file ? file.name : 'Выберите видео или аудио'}</strong>
            <span>MP4, WebM, MOV, MKV, MP3 и другие · до 4 ГБ</span>
            <input
              type="file"
              accept=".mp4,.m4v,.webm,.mov,.mkv,.mp3,.m4a,.wav,.ogg"
              required
              onChange={(e) => setFile(e.target.files[0])}
            />
          </label>
        )}
        <label>
          Название{' '}
          {tab !== 'course' && <span className="muted">· необязательно</span>}
          <input
            name="title"
            maxLength={300}
            required={tab === 'course'}
            placeholder={
              tab === 'course' ? 'Название курса' : 'Название лекции'
            }
          />
        </label>
        {tab === 'course' ? (
          <label>
            Описание
            <textarea name="description" rows={3} />
          </label>
        ) : (
          <label>
            Курс
            <select name="course_id">
              <option value="">Без курса</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </label>
        )}
        <button disabled={busy} className="button primary full">
          {busy ? <Spinner /> : <Plus size={18} />}{' '}
          {tab === 'course'
            ? 'Создать курс'
            : busy
              ? 'Отправляем материал…'
              : 'Добавить лекцию'}
        </button>
        <p className="fine-print">
          {tab === 'file'
            ? 'Сначала передадим файл, затем начнётся обработка. Не закрывайте окно во время передачи.'
            : 'Обработка начнётся после добавления. Её этапы появятся на странице лекции.'}
        </p>
      </form>
    </Modal>
  );
}

export function ProfileModal({ user, onClose, onChange, onLogout }) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(null),
    [saved, setSaved] = useState(false);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onChange(
        await api('/users/me', {
          method: 'PATCH',
          body: Object.fromEntries(new FormData(e.currentTarget)),
        }),
      );
      setSaved(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  async function avatar(e) {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      setError(new Error('Аватар должен быть меньше 5 МБ.'));
      return;
    }
    setBusy(true);
    try {
      const body = new FormData();
      body.set('file', file);
      onChange(await api('/users/me/avatar', { method: 'PUT', body }));
      setSaved(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Ваш профиль" subtitle={user.email} onClose={onClose}>
      <ErrorNotice error={error} />
      <div className="profile-avatar">
        <span className="avatar large">
          {user.avatar_url ? (
            <img src={`${user.avatar_url}?v=${Date.now()}`} alt="Ваш аватар" />
          ) : (
            <UserCircle size={36} />
          )}
        </span>
        <label className="button secondary">
          Изменить фото
          <input
            className="sr-only"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={avatar}
            disabled={busy}
          />
        </label>
        {user.avatar_url && (
          <button
            className="text-button"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api('/users/me/avatar', { method: 'DELETE' });
                onChange({ ...user, avatar_url: null });
              } catch (err) {
                setError(err);
              } finally {
                setBusy(false);
              }
            }}
          >
            Удалить
          </button>
        )}
      </div>
      <form onSubmit={submit} className="form">
        <div className="form-row">
          <label>
            Имя
            <input
              name="first_name"
              defaultValue={user.first_name}
              required
              maxLength={100}
            />
          </label>
          <label>
            Фамилия
            <input
              name="last_name"
              defaultValue={user.last_name}
              required
              maxLength={100}
            />
          </label>
        </div>
        <div className="role-label">
          {user.role === 'teacher' ? 'Преподаватель' : 'Студент'}
        </div>
        <button className="button primary" disabled={busy}>
          {busy ? <Spinner /> : saved ? <CheckCircle size={18} /> : null}
          {saved ? 'Изменения сохранены' : 'Сохранить'}
        </button>
      </form>
      <div className="profile-logout">
        <button className="text-button danger" onClick={onLogout}>
          Выйти из аккаунта
        </button>
      </div>
    </Modal>
  );
}

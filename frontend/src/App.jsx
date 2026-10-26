import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Asterisk,
  House,
  BookOpenText,
  Compass,
  BookmarkSimple,
  MagnifyingGlass,
  GearSix,
  Question,
  CaretRight,
  CaretDown,
  CheckCircle,
  PlayCircle,
  Clock,
  ShareNetwork,
  Lightning,
  Waveform,
  ArrowUpRight,
  ArrowRight,
  Play,
  Pause,
  SpeakerHigh,
  SpeakerSlash,
  CornersOut,
  Plus,
  X,
  ArrowLeft,
  FileVideo,
  Check,
  CircleNotch,
  PaperPlaneTilt,
  DownloadSimple,
  PencilSimple,
  Trash,
  UserCircle,
  Stack,
  GraduationCap,
  ArrowClockwise,
  WarningCircle,
  List,
  TextAlignLeft,
  ChatCircleDots,
  DotsThree,
} from '@phosphor-icons/react';
import ReactMarkdown from 'react-markdown';
import {
  api,
  setAccessToken,
  refreshSession,
  time,
  duration,
  statuses,
} from './lib/api';
import {
  demoCourse,
  demoLectures,
  demoSegments,
  demoSummary,
  loadDemoState,
} from './lib/demo';
import {
  Modal,
  AuthModal,
  SearchModal,
  UploadModal,
  ProfileModal,
  ErrorNotice,
  Empty,
  Spinner,
} from './components';

const navItems = [
  ['dashboard', House, 'Главная'],
  ['courses', BookOpenText, 'Мои курсы'],
  ['catalog', Compass, 'Каталог лекций'],
  ['favorites', BookmarkSimple, 'Избранное'],
  ['bookmarks', Stack, 'Мои заметки'],
];
function getRoute() {
  const hash = location.hash.slice(1);
  const match = hash.match(/^\/lecture\/([^?]+)/);
  return match
    ? {
        id: decodeURIComponent(match[1]),
        seconds: Number(new URLSearchParams(hash.split('?')[1]).get('t')) || 0,
      }
    : null;
}
function lectureCount(n) {
  const a = n % 10,
    b = n % 100;
  return `${n} ${a === 1 && b !== 11 ? 'лекция' : a >= 2 && a <= 4 && (b < 12 || b > 14) ? 'лекции' : 'лекций'}`;
}
function Markdown({ children, sources, onSeek }) {
  const content = sources
    ? (children || '').replace(/\[(\d+)\](?!\()/g, '[$1](#source-$1)')
    : children;
  return (
    <div className="markdown">
      <ReactMarkdown
        skipHtml
        components={{
          h1: ({ children }) => <h2>{children}</h2>,
          a: ({ href, children }) => {
            const match = href?.match(/^#source-(\d+)$/);
            const source = match && sources?.[Number(match[1]) - 1];
            return source ? (
              <button className="inline-source" onClick={() => onSeek(source)}>
                {children}
              </button>
            ) : (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {content || ''}
      </ReactMarkdown>
    </div>
  );
}

export function App() {
  const route = useRef(getRoute());
  const [view, setView] = useState('lecture'),
    [lectureId, setLectureId] = useState(route.current?.id || 'demo-1');
  const demo = lectureId.startsWith('demo-');
  const [lecture, setLecture] = useState(demoLectures[0]),
    [course, setCourse] = useState(demoCourse),
    [playlist, setPlaylist] = useState(demoLectures);
  const [segments, setSegments] = useState(demoSegments),
    [summary, setSummary] = useState(demoSummary),
    [author, setAuthor] = useState(null);
  const [user, setUser] = useState(null),
    [personal, setPersonal] = useState({ bookmarks: [] }),
    [library, setLibrary] = useState([]),
    [courses, setCourses] = useState([]),
    [revision, setRevision] = useState(0),
    [lectureRevision, setLectureRevision] = useState(0);
  const [busy, setBusy] = useState(false),
    [pageError, setPageError] = useState(null),
    [libraryError, setLibraryError] = useState(null),
    [connected, setConnected] = useState(null);
  const [modal, setModal] = useState(null),
    [mobileMenu, setMobileMenu] = useState(false),
    [tab, setTab] = useState('overview'),
    [rightTab, setRightTab] = useState('notes');
  const [position, setPosition] = useState(route.current?.seconds || 0),
    [playing, setPlaying] = useState(false),
    [muted, setMuted] = useState(false),
    [speed, setSpeed] = useState(1),
    [videoError, setVideoError] = useState(false);
  const [toast, setToast] = useState(null),
    [actionBusy, setActionBusy] = useState(false),
    [note, setNote] = useState(''),
    [listFilter, setListFilter] = useState(''),
    [statusFilter, setStatusFilter] = useState('');
  const [collection, setCollection] = useState(null),
    [collectionError, setCollectionError] = useState(null),
    [collectionBusy, setCollectionBusy] = useState(false);
  const [question, setQuestion] = useState(''),
    [messages, setMessages] = useState([]),
    [chatBusy, setChatBusy] = useState(false),
    [chatError, setChatError] = useState(null);
  const [transcriptQuery, setTranscriptQuery] = useState(''),
    [demoSaved, setDemoSaved] = useState(loadDemoState);
  const lastPositions = useRef({});
  const video = useRef(),
    videoWrap = useRef(),
    seekTarget = useRef(route.current?.seconds || 0),
    saveQueue = useRef(Promise.resolve()),
    positionRef = useRef(0),
    playingRef = useRef(false),
    chatAbort = useRef(),
    toastTimer = useRef(),
    chatEnd = useRef();
  positionRef.current = position;
  playingRef.current = playing;
  const notify = useCallback((message) => {
    setToast(message);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4200);
  }, []);
  const bump = () => setRevision((r) => r + 1);
  const openLecture = useCallback(
    (id, seconds = 0) => {
      seekTarget.current = seconds;
      setPosition(seconds);
      setPlaying(false);
      setView('lecture');
      setTab('overview');
      setLectureId(id);
      setMobileMenu(false);
      location.hash = `/lecture/${encodeURIComponent(id)}${seconds ? `?t=${Math.floor(seconds)}` : ''}`;
      if (id === lectureId && video.current?.readyState)
        video.current.currentTime = seconds;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },
    [lectureId],
  );
  const navigate = (id) => {
    setCollection(null);
    setCollectionBusy(true);
    setView(id);
    setMobileMenu(false);
    setListFilter('');
    setStatusFilter('');
  };
  useEffect(() => {
    function hashChange() {
      const r = getRoute();
      if (r) {
        seekTarget.current = r.seconds;
        setLectureId(r.id);
        setPosition(r.seconds);
        setView('lecture');
      }
    }
    window.addEventListener('hashchange', hashChange);
    return () => window.removeEventListener('hashchange', hashChange);
  }, []);
  useEffect(() => {
    let active = true;
    refreshSession().then(async (ok) => {
      if (ok) {
        try {
          const u = await api('/auth/me');
          if (active) setUser(u);
        } catch {}
      }
    });
    const expired = () => {
      setUser(null);
      setPersonal({ bookmarks: [] });
    };
    window.addEventListener('lectio:session-expired', expired);
    return () => {
      active = false;
      window.removeEventListener('lectio:session-expired', expired);
    };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api('/lectures?limit=200', { signal: controller.signal }),
      api('/courses', { signal: controller.signal }),
    ])
      .then(([l, c]) => {
        setLibrary(l);
        setCourses(c);
        setConnected(true);
        setLibraryError(null);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setLibraryError(err);
          setConnected(false);
        }
      });
    return () => controller.abort();
  }, [revision]);
  useEffect(() => {
    const controller = new AbortController();
    setPageError(null);
    setVideoError(false);
    setMessages([]);
    setChatError(null);
    setRightTab('notes');
    chatAbort.current?.abort();
    setChatBusy(false);
    if (demo) {
      setLecture(
        demoLectures.find((l) => l.id === lectureId) || demoLectures[0],
      );
      setCourse(demoCourse);
      setPlaylist(demoLectures);
      setSegments(demoSegments);
      setSummary(demoSummary);
      setAuthor(null);
      setBusy(false);
      return;
    }
    setBusy(true);
    setSegments([]);
    setSummary(null);
    setPersonal({ bookmarks: [] });
    setCourse(null);
    setPlaylist([]);
    setAuthor(null);
    async function load() {
      try {
        const l = await api(`/lectures/${lectureId}`, {
          signal: controller.signal,
        });
        setLecture(l);
        const results = await Promise.allSettled([
          l.course_id
            ? api(`/courses/${l.course_id}`, { signal: controller.signal })
            : Promise.resolve(null),
          api(
            `/lectures?${l.course_id ? `course_id=${l.course_id}&` : ''}limit=200`,
            { signal: controller.signal },
          ),
          ['ready', 'summarizing'].includes(l.status)
            ? api(`/lectures/${l.id}/segments`, { signal: controller.signal })
            : Promise.resolve([]),
          api(`/lectures/${l.id}/summary`, { signal: controller.signal }),
          l.owner_id
            ? api(`/users/${l.owner_id}`, { signal: controller.signal })
            : Promise.resolve(null),
        ]);
        if (controller.signal.aborted) return;
        const setters = [
          setCourse,
          setPlaylist,
          setSegments,
          setSummary,
          setAuthor,
        ];
        results.forEach((r, i) => {
          if (r.status === 'fulfilled') setters[i](r.value);
          else if (i === 2 || i === 3)
            notify(
              i === 2
                ? 'Не удалось загрузить расшифровку. Обновите страницу.'
                : 'Не удалось загрузить конспект. Обновите страницу.',
            );
        });
      } catch (err) {
        if (err.name !== 'AbortError') setPageError(err);
      } finally {
        if (!controller.signal.aborted) setBusy(false);
      }
    }
    load();
    return () => controller.abort();
  }, [lectureId, demo, lectureRevision]);
  useEffect(() => {
    if (demo || !user) {
      setPersonal({ bookmarks: [] });
      return;
    }
    let active = true;
    api(`/lectures/${lectureId}/me`)
      .then((data) => {
        if (!active) return;
        setPersonal(data);
        if (!seekTarget.current && data.progress.position_seconds) {
          seekTarget.current = data.progress.position_seconds;
          setPosition(data.progress.position_seconds);
          if (video.current?.readyState)
            video.current.currentTime = data.progress.position_seconds;
        }
      })
      .catch((err) => {
        if (active) notify(err.message);
      });
    return () => {
      active = false;
    };
  }, [lectureId, user, demo, revision]);
  useEffect(() => {
    if (
      demo ||
      view !== 'lecture' ||
      !lecture ||
      ['ready', 'failed'].includes(lecture.status)
    )
      return;
    const poll = setInterval(async () => {
      if (document.hidden) return;
      try {
        const data = await api(`/lectures/${lectureId}`);
        setLecture(data);
        if (['ready', 'failed'].includes(data.status)) {
          setLectureRevision((r) => r + 1);
          setRevision((r) => r + 1);
        }
      } catch {}
    }, 4000);
    return () => clearInterval(poll);
  }, [demo, view, lectureId, lecture?.status]);
  useEffect(() => {
    localStorage.setItem('lectio:demo', JSON.stringify(demoSaved));
  }, [demoSaved]);
  useEffect(() => {
    chatEnd.current?.scrollIntoView({ block: 'nearest' });
  }, [messages, chatBusy]);
  useEffect(
    () => () => {
      chatAbort.current?.abort();
      clearTimeout(toastTimer.current);
    },
    [],
  );
  const saveProgress = useCallback(
    (seconds, completed) => {
      if (demo || !user || !lectureId) return;
      saveQueue.current = saveQueue.current
        .catch(() => {})
        .then(() =>
          api(`/lectures/${lectureId}/progress`, {
            method: 'PUT',
            body: {
              position_seconds: seconds,
              ...(completed === undefined ? {} : { completed }),
            },
          }),
        )
        .then((result) => {
          if (completed !== undefined)
            setPersonal((p) => ({ ...p, progress: result }));
        })
        .catch((err) => notify(`Прогресс не сохранён: ${err.message}`));
    },
    [demo, user, lectureId, notify],
  );
  useEffect(() => {
    const id = setInterval(() => {
      if (playingRef.current) saveProgress(positionRef.current);
    }, 8000);
    return () => clearInterval(id);
  }, [saveProgress]);
  useEffect(() => {
    const id = lectureId;
    const save = () => {
      if (document.hidden && lastPositions.current[id] != null)
        saveProgress(lastPositions.current[id]);
    };
    document.addEventListener('visibilitychange', save);
    return () => {
      document.removeEventListener('visibilitychange', save);
      if (lastPositions.current[id] != null)
        saveProgress(lastPositions.current[id]);
    };
  }, [saveProgress, lectureId]);
  useEffect(() => {
    if (view === 'lecture' || view === 'catalog') return;
    if (!user) {
      setCollection(null);
      return;
    }
    const controller = new AbortController();
    setCollection(null);
    setCollectionBusy(true);
    setCollectionError(null);
    const path = {
      dashboard: '/me/dashboard',
      courses: '/me/courses',
      favorites: '/me/favorites',
      bookmarks: '/me/bookmarks',
      teacher: `/lectures?owner_id=${user.id}&limit=200`,
    }[view];
    if (!path) {
      setCollectionBusy(false);
      return;
    }
    api(path, { signal: controller.signal })
      .then(setCollection)
      .catch((err) => {
        if (err.name !== 'AbortError') setCollectionError(err);
      })
      .finally(() => {
        if (!controller.signal.aborted) setCollectionBusy(false);
      });
    return () => controller.abort();
  }, [view, user, revision]);
  function seek(seconds) {
    const value = Math.max(
      0,
      Math.min(seconds, lecture?.duration_seconds || Infinity),
    );
    setPosition(value);
    seekTarget.current = value;
    if (video.current?.readyState) {
      video.current.currentTime = value;
      lastPositions.current[lectureId] = value;
    }
  }
  async function togglePlay() {
    if (demo) {
      setModal('demo-video');
      return;
    }
    if (!video.current?.getAttribute('src')) return;
    try {
      if (video.current.paused) await video.current.play();
      else video.current.pause();
    } catch {
      setVideoError(true);
    }
  }
  const requireUser = (fn) => {
    if (!user) {
      setModal('auth');
      return;
    }
    return fn();
  };
  const favorite = demo
    ? !!demoSaved.favorites?.includes(lectureId)
    : !!personal.is_favorite;
  const bookmarks = demo
    ? (demoSaved.bookmarks || []).filter((b) => b.lecture_id === lectureId)
    : personal.bookmarks || [];
  async function toggleFavorite() {
    if (demo) {
      setDemoSaved((s) => ({
        ...s,
        favorites: favorite
          ? (s.favorites || []).filter((id) => id !== lectureId)
          : [...(s.favorites || []), lectureId],
      }));
      notify(
        favorite ? 'Убрано из демо-избранного' : 'Добавлено в демо-избранное',
      );
      return;
    }
    requireUser(async () => {
      setActionBusy(true);
      try {
        await api(`/lectures/${lectureId}/favorite`, {
          method: favorite ? 'DELETE' : 'PUT',
        });
        setPersonal((p) => ({ ...p, is_favorite: !favorite }));
        bump();
      } catch (err) {
        notify(err.message);
      } finally {
        setActionBusy(false);
      }
    });
  }
  async function addBookmark(e) {
    e.preventDefault();
    setActionBusy(true);
    try {
      const body = { position_seconds: position, note: note.trim() || null };
      if (demo) {
        const b = {
          ...body,
          id: crypto.randomUUID(),
          lecture_id: lectureId,
          lecture_title: lecture.title,
        };
        setDemoSaved((s) => ({ ...s, bookmarks: [...(s.bookmarks || []), b] }));
      } else {
        if (!user) {
          setModal('auth');
          return;
        }
        const b = await api(`/lectures/${lectureId}/bookmarks`, {
          method: 'POST',
          body,
        });
        setPersonal((p) => ({ ...p, bookmarks: [...(p.bookmarks || []), b] }));
        bump();
      }
      setNote('');
      notify('Заметка сохранена');
    } catch (err) {
      notify(err.message);
    } finally {
      setActionBusy(false);
    }
  }
  async function removeBookmark(id, isDemo = demo) {
    setActionBusy(true);
    try {
      if (isDemo)
        setDemoSaved((s) => ({
          ...s,
          bookmarks: (s.bookmarks || []).filter((b) => b.id !== id),
        }));
      else {
        await api(`/bookmarks/${id}`, { method: 'DELETE' });
        bump();
      }
      notify('Заметка удалена');
    } catch (err) {
      notify(err.message);
    } finally {
      setActionBusy(false);
    }
  }
  async function enrollment() {
    requireUser(async () => {
      if (!course) return;
      setActionBusy(true);
      try {
        await api(`/courses/${course.id}/enrollment`, {
          method: personal.is_enrolled_in_course ? 'DELETE' : 'PUT',
        });
        setPersonal((p) => ({
          ...p,
          is_enrolled_in_course: !p.is_enrolled_in_course,
        }));
        notify(
          personal.is_enrolled_in_course
            ? 'Вы отписались от курса'
            : 'Курс добавлен в «Мои курсы»',
        );
        bump();
      } catch (err) {
        notify(err.message);
      } finally {
        setActionBusy(false);
      }
    });
  }
  async function ask(e, preset) {
    e?.preventDefault();
    const q = (preset || question).trim();
    if (!q || chatBusy) return;
    setQuestion('');
    setChatError(null);
    setChatBusy(true);
    setRightTab('chat');
    const history = messages
      .flatMap((m) => [
        { role: 'user', content: m.question.slice(0, 8000) },
        ...(m.answer
          ? [{ role: 'assistant', content: m.answer.slice(0, 8000) }]
          : []),
      ])
      .slice(-20);
    setMessages((m) => [...m, { question: q }]);
    chatAbort.current = new AbortController();
    try {
      if (demo) {
        setMessages((m) =>
          m.map((x, i) =>
            i === m.length - 1
              ? {
                  ...x,
                  answer:
                    'Это пример ответа в демо-курсе. Дизайн-мышление состоит из пяти этапов: эмпатия, фокусировка, генерация идей, прототипирование и тестирование. Начинайте с потребностей человека и проверяйте решения через прототипы.',
                  sources: [
                    {
                      lecture_id: lectureId,
                      start_seconds: 96,
                      text: 'Пять этапов дизайн-мышления',
                    },
                  ],
                }
              : x,
          ),
        );
      } else {
        const answer = await api('/qa', {
          method: 'POST',
          body: { question: q, lecture_id: lectureId, history },
          signal: chatAbort.current.signal,
        });
        setMessages((m) =>
          m.map((x, i) => (i === m.length - 1 ? { ...x, ...answer } : x)),
        );
      }
    } catch (err) {
      if (err.name !== 'AbortError') setChatError(err);
      else notify('Ожидание ответа остановлено');
      setMessages((m) => m.filter((x) => x.answer));
    } finally {
      setChatBusy(false);
    }
  }
  function downloadSummary() {
    if (!summary?.summary) return;
    const url = URL.createObjectURL(
      new Blob([summary.summary], { type: 'text/markdown;charset=utf-8' }),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = `${lecture.title}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }
  async function share() {
    const url = `${location.origin}${location.pathname}#/lecture/${lectureId}?t=${Math.floor(position)}`;
    try {
      await navigator.clipboard.writeText(url);
      notify('Ссылка с таймкодом скопирована');
    } catch {
      setModal({ type: 'share', url });
    }
  }
  async function logout() {
    try {
      await api('/auth/logout', { method: 'POST' });
    } catch (err) {
      notify(err.message);
    }
    setAccessToken(null);
    setUser(null);
    setPersonal({ bookmarks: [] });
    setCollection(null);
    setModal(null);
    notify('Вы вышли из аккаунта');
  }
  const activeNav = view === 'lecture' ? 'courses' : view;
  const overviewTitle = demo
    ? demoCourse.title
    : course?.title || lecture?.title;
  const canRead = demo || ['ready', 'summarizing'].includes(lecture?.status);
  const filteredSegments = segments.filter((s) =>
    s.text.toLowerCase().includes(transcriptQuery.toLowerCase()),
  );
  const courseOptions = courses.filter(
    (c) => user?.role === 'teacher' && (!c.owner_id || c.owner_id === user.id),
  );

  function renderLectureCard(l) {
    return (
      <button
        className="lecture-card"
        key={l.id}
        onClick={() => openLecture(l.id)}
      >
        <span
          className={`lecture-cover ${l.id.startsWith('demo') ? 'has-photo' : ''}`}
        >
          {l.id.startsWith('demo') ? (
            <img src="/assets/lecture-poster.png" alt="Преподаватель курса" />
          ) : (
            <FileVideo size={44} weight="light" />
          )}
          <span className="card-play">
            <Play size={17} weight="fill" />
          </span>
          <span className="card-duration">{time(l.duration_seconds)}</span>
        </span>
        <div className="lecture-card-body">
          <span className="eyebrow">
            {l.id.startsWith('demo')
              ? 'ЗНАКОМСТВО С LECTIO'
              : statuses[l.status]}
          </span>
          <h3>{l.title}</h3>
          <div className="card-meta">
            <Clock size={15} />
            {duration(l.duration_seconds)}
            <span>
              Открыть лекцию <ArrowUpRight size={15} />
            </span>
          </div>
        </div>
      </button>
    );
  }
  function renderCollections() {
    const titles = {
      dashboard: 'Ваше пространство для знаний',
      courses: 'Мои курсы',
      catalog: 'Каталог лекций',
      favorites: 'Избранные лекции',
      bookmarks: 'Мои заметки',
      teacher: 'Мои материалы',
    };
    const descriptions = {
      dashboard: 'Возвращайтесь к важному. Двигайтесь в своём темпе.',
      courses: 'Всё, что вы изучаете, в одном месте.',
      catalog: 'Исследуйте библиотеку и находите новые идеи.',
      favorites: 'Лекции, к которым хочется вернуться.',
      bookmarks: 'Ваши мысли и важные моменты из лекций.',
      teacher: 'Делитесь знаниями. Всю рутину Lectio возьмёт на себя.',
    };
    let data = view === 'catalog' ? library : collection;
    const filtered = Array.isArray(data)
      ? data.filter(
          (l) =>
            l.title?.toLowerCase().includes(listFilter.toLowerCase()) &&
            (!statusFilter || l.status === statusFilter),
        )
      : [];
    return (
      <>
        <section className="page-heading panel">
          <div className="eyebrow">ВАШЕ ОБУЧЕНИЕ</div>
          <div className="heading-row">
            <div>
              <h1>{titles[view]}</h1>
              <p>{descriptions[view]}</p>
            </div>
            {user?.role === 'teacher' && (
              <button
                className="button primary"
                onClick={() => setModal('upload')}
              >
                <Plus size={19} />
                Добавить материал
              </button>
            )}
          </div>
        </section>
        <section className="collection-panel panel">
          {view !== 'catalog' && !user ? (
            <Empty icon={UserCircle} title="Сохраните свой прогресс">
              Войдите, чтобы видеть ваши курсы, избранное и заметки.
              <button
                className="button primary"
                onClick={() => setModal('auth')}
              >
                Войти в Lectio
                <ArrowRight size={17} />
              </button>
            </Empty>
          ) : (
            <>
              <ErrorNotice
                error={view === 'catalog' ? libraryError : collectionError}
              />
              {collectionBusy && view !== 'catalog' ? (
                <div className="loading-block">
                  <Spinner />
                  Загружаем ваши материалы…
                </div>
              ) : (
                <>
                  {view === 'dashboard' && collection?.continue_watching && (
                    <>
                      <div className="stats-grid">
                        {[
                          [
                            BookOpenText,
                            'Курсов в обучении',
                            collection.enrolled_courses,
                          ],
                          [
                            CheckCircle,
                            'Лекций завершено',
                            collection.lectures_completed,
                          ],
                          [
                            Clock,
                            'Позиции просмотра',
                            duration(collection.watched_seconds),
                          ],
                          [BookmarkSimple, 'В избранном', collection.favorites],
                        ].map(([Icon, label, value]) => (
                          <div className="stat" key={label}>
                            <Icon size={23} />
                            <strong>{value}</strong>
                            <span>{label}</span>
                          </div>
                        ))}
                      </div>
                      <p className="fine-print">
                        Позиции просмотра — сумма сохранённых позиций в лекциях,
                        а не точное время обучения.
                      </p>
                      <h2>Продолжить обучение</h2>
                      <div className="card-grid">
                        {collection.continue_watching.map((item) =>
                          renderLectureCard(item.lecture),
                        )}
                      </div>
                      {!collection.continue_watching.length && (
                        <Empty title="Впереди много интересного">
                          Откройте первую лекцию в каталоге.
                          <button
                            className="button secondary"
                            onClick={() => navigate('catalog')}
                          >
                            В каталог
                            <ArrowRight size={17} />
                          </button>
                        </Empty>
                      )}
                      <h2>Недавние запросы</h2>
                      <div className="recent-searches">
                        {collection.recent_searches.length ? (
                          collection.recent_searches.map((s) => (
                            <button
                              className="button secondary"
                              key={s.query}
                              onClick={() => {
                                setModal({
                                  type: 'search',
                                  initialQuery: s.query,
                                });
                              }}
                            >
                              <MagnifyingGlass size={16} />
                              {s.query}
                            </button>
                          ))
                        ) : (
                          <p className="muted">
                            Здесь появятся ваши поисковые запросы.
                          </p>
                        )}
                      </div>
                    </>
                  )}
                  {view === 'courses' && (
                    <>
                      {!collection?.length ? (
                        <Empty
                          icon={BookOpenText}
                          title="Ваш первый курс ждёт вас"
                        >
                          Откройте каталог и запишитесь на интересный курс.
                          <button
                            className="button primary"
                            onClick={() => navigate('catalog')}
                          >
                            Найти курс
                            <ArrowRight size={17} />
                          </button>
                        </Empty>
                      ) : (
                        <div className="course-grid">
                          {collection.map((c) => (
                            <button
                              className="course-card"
                              key={c.id}
                              onClick={async () => {
                                try {
                                  const ls = await api(
                                    `/lectures?course_id=${c.id}&limit=200`,
                                  );
                                  if (ls.length) openLecture(ls[0].id);
                                  else notify('В этом курсе пока нет лекций.');
                                } catch (err) {
                                  notify(err.message);
                                }
                              }}
                            >
                              <BookOpenText size={30} weight="light" />
                              <h3>{c.title}</h3>
                              <p>{c.description || 'Курс лекций'}</p>
                              <div className="course-progress">
                                <progress max="1" value={c.progress} />
                                <span>
                                  {c.completed_lectures} из {c.lectures_count}{' '}
                                  лекций
                                </span>
                              </div>
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                  {['catalog', 'favorites', 'teacher'].includes(view) && (
                    <>
                      <div className="collection-toolbar">
                        <div className="filter-input">
                          <MagnifyingGlass size={19} />
                          <input
                            aria-label="Фильтр по названию"
                            placeholder="Найти по названию…"
                            value={listFilter}
                            onChange={(e) => setListFilter(e.target.value)}
                          />
                        </div>
                        <select
                          aria-label="Статус лекции"
                          value={statusFilter}
                          onChange={(e) => setStatusFilter(e.target.value)}
                        >
                          <option value="">Все статусы</option>
                          {Object.entries(statuses).map(([id, label]) => (
                            <option key={id} value={id}>
                              {label}
                            </option>
                          ))}
                        </select>
                        <button
                          className="icon-button"
                          onClick={bump}
                          aria-label="Обновить библиотеку"
                        >
                          <ArrowClockwise size={20} />
                        </button>
                      </div>
                      {view === 'catalog' && courses.length > 0 && (
                        <div className="course-chips">
                          {courses.map((c) => (
                            <button
                              className="button secondary"
                              key={c.id}
                              onClick={async () => {
                                try {
                                  const ls = await api(
                                    `/lectures?course_id=${c.id}&limit=200`,
                                  );
                                  if (ls.length) openLecture(ls[0].id);
                                  else notify('В этом курсе пока нет лекций.');
                                } catch (err) {
                                  notify(err.message);
                                }
                              }}
                            >
                              <BookOpenText size={17} />
                              {c.title}
                              <span>{c.lectures_count}</span>
                            </button>
                          ))}
                        </div>
                      )}
                      <div className="card-grid">
                        {filtered.map(renderLectureCard)}
                      </div>
                      {!filtered.length && !libraryError && (
                        <Empty
                          icon={FileVideo}
                          title={
                            listFilter || statusFilter
                              ? 'Ничего не найдено'
                              : 'Здесь пока нет лекций'
                          }
                        >
                          {listFilter || statusFilter
                            ? 'Попробуйте изменить фильтры.'
                            : view === 'favorites'
                              ? 'Сохраняйте интересные лекции кнопкой рядом с плеером.'
                              : 'Добавленные материалы появятся здесь.'}
                        </Empty>
                      )}
                      {view === 'catalog' && (
                        <div className="demo-library">
                          <div>
                            <span className="eyebrow">
                              ПОСМОТРИТЕ, КАК ЭТО РАБОТАЕТ
                            </span>
                            <h3>Познакомьтесь с Lectio на демо-курсе</h3>
                            <p>
                              Конспекты, таймкоды и заметки — попробуйте всё
                              сами.
                            </p>
                          </div>
                          <button
                            className="button secondary"
                            onClick={() => openLecture('demo-1')}
                          >
                            Открыть демо
                            <ArrowUpRight size={18} />
                          </button>
                        </div>
                      )}
                    </>
                  )}
                  {view === 'bookmarks' && (
                    <>
                      {collection?.length ? (
                        collection.map((b) => (
                          <div className="saved-note" key={b.id}>
                            <button
                              className="timecode"
                              onClick={() =>
                                openLecture(b.lecture_id, b.position_seconds)
                              }
                            >
                              {time(b.position_seconds)}
                            </button>
                            <div>
                              <strong>{b.lecture_title}</strong>
                              <p>{b.note || 'Без заметки'}</p>
                            </div>
                            <button
                              className="icon-button"
                              aria-label="Редактировать заметку"
                              onClick={() =>
                                setModal({
                                  type: 'edit-bookmark',
                                  bookmark: b,
                                  demo: false,
                                })
                              }
                            >
                              <PencilSimple size={18} />
                            </button>
                            <button
                              className="icon-button danger"
                              aria-label="Удалить заметку"
                              disabled={actionBusy}
                              onClick={() => removeBookmark(b.id, false)}
                            >
                              <Trash size={18} />
                            </button>
                          </div>
                        ))
                      ) : (
                        <Empty icon={Stack} title="Поймайте важную мысль">
                          Сохраняйте заметки к любому моменту лекции.
                        </Empty>
                      )}
                    </>
                  )}
                </>
              )}
            </>
          )}
        </section>
      </>
    );
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        К содержимому
      </a>
      {mobileMenu && (
        <div className="sidebar-scrim" onClick={() => setMobileMenu(false)} />
      )}
      <aside className={`sidebar ${mobileMenu ? 'open' : ''}`}>
        <button
          className="brand"
          onClick={() => openLecture('demo-1')}
          aria-label="Lectio — открыть демо"
        >
          <span className="brand-symbol">
            <Asterisk size={29} weight="light" />
          </span>
          <span className="brand-text">
            Lectio<small>Пространство знаний</small>
          </span>
          <CaretRight size={17} className="brand-arrow" />
        </button>
        <div className="nav-section-label">Моё обучение</div>
        <nav aria-label="Основная навигация">
          {navItems.map(([id, Icon, label]) => (
            <button
              key={id}
              className={`nav-item ${activeNav === id ? 'active' : ''}`}
              onClick={() => navigate(id)}
            >
              <Icon size={21} weight={activeNav === id ? 'regular' : 'light'} />
              <span>{label}</span>
            </button>
          ))}
          <button className="nav-item" onClick={() => setModal('search')}>
            <MagnifyingGlass size={21} weight="light" />
            <span>Умный поиск</span>
            <kbd>⌘ K</kbd>
          </button>
          {user?.role === 'teacher' && (
            <button
              className={`nav-item ${view === 'teacher' ? 'active' : ''}`}
              onClick={() => navigate('teacher')}
            >
              <GraduationCap size={21} />
              <span>Мои материалы</span>
            </button>
          )}
        </nav>
        <div className="nav-divider" />
        <div className="nav-section-label secondary-label">Настройки</div>
        <button
          className="nav-item"
          onClick={() => setModal(user ? 'profile' : 'auth')}
        >
          <GearSix size={21} weight="light" />
          <span>Настройки профиля</span>
        </button>
        <button className="nav-item" onClick={() => setModal('help')}>
          <Question size={21} weight="light" />
          <span>Помощь</span>
          <ArrowUpRight size={15} />
        </button>
        <div className="sidebar-bottom">
          <div className="sidebar-promo">
            <span className="promo-icon">
              <Lightning size={19} weight="light" />
            </span>
            <h3>Знания, которые остаются</h3>
            <p>
              Смотрите. Спрашивайте.
              <br />
              Возвращайтесь к важному.
            </p>
            <button onClick={() => setModal('search')}>
              Попробовать умный поиск
              <ArrowUpRight size={15} />
            </button>
          </div>
          <button
            className="user-menu"
            onClick={() => setModal(user ? 'profile' : 'auth')}
          >
            <span className="avatar">
              {user?.avatar_url ? (
                <img src={user.avatar_url} alt="" />
              ) : user ? (
                `${user.first_name[0]}${user.last_name[0]}`
              ) : (
                <UserCircle size={27} weight="light" />
              )}
            </span>
            <span>
              <strong>
                {user ? `${user.first_name} ${user.last_name}` : 'Гость Lectio'}
              </strong>
              <small>
                {user
                  ? user.role === 'teacher'
                    ? 'Преподаватель'
                    : 'Студент'
                  : 'Войти в аккаунт'}
              </small>
            </span>
            <CaretDown size={16} />
          </button>
          <div className="sidebar-footnote">
            <span className={`connection-dot ${connected ? 'online' : ''}`} />
            {connected === null
              ? 'Подключаемся…'
              : connected
                ? 'Сервер подключён'
                : 'Сервер недоступен'}
            <span>v1.0</span>
          </div>
        </div>
      </aside>
      <main className="main-content" id="main-content">
        <div className="topbar">
          <button
            className="icon-button mobile-toggle"
            aria-label="Открыть меню"
            onClick={() => setMobileMenu(!mobileMenu)}
          >
            <List size={22} />
          </button>
          <div className="topbar-location">
            <GraduationCap size={18} weight="light" />
            <span>Учиться — значит открывать</span>
          </div>
          <div className="topbar-actions">
            {demo && view === 'lecture' && (
              <span className="demo-badge">Демо-курс</span>
            )}
            <button className="top-search" onClick={() => setModal('search')}>
              <MagnifyingGlass size={17} />
              <span>Поиск по знаниям</span>
              <kbd>⌘ K</kbd>
            </button>
            {!user && (
              <button className="top-login" onClick={() => setModal('auth')}>
                Войти
                <ArrowUpRight size={16} />
              </button>
            )}
          </div>
        </div>
        {view !== 'lecture' ? (
          renderCollections()
        ) : (
          <>
            <section className="course-heading panel">
              <div className="breadcrumbs">
                <button onClick={() => navigate('courses')}>Мои курсы</button>
                <CaretRight size={14} />
                <button onClick={() => navigate('catalog')}>
                  {demo ? 'Дизайн' : 'Библиотека'}
                </button>
                <CaretRight size={14} />
                <span>{demo ? 'Основы' : course ? 'Курс' : 'Лекция'}</span>
              </div>
              <div className="heading-row">
                <div className="heading-text">
                  <h1>{busy ? 'Загружаем лекцию…' : overviewTitle}</h1>
                  <div className="course-meta">
                    <span>
                      <PlayCircle size={18} />
                      {lectureCount(demo ? 5 : course?.lectures_count || 1)}
                    </span>
                    <i />
                    <span>
                      <Clock size={18} />
                      {duration(
                        demo
                          ? demoCourse.total_duration_seconds
                          : course?.total_duration_seconds ||
                              lecture?.duration_seconds,
                      )}
                    </span>
                    <i />
                    <span>
                      <TextAlignLeft size={18} />
                      {demo
                        ? 'С конспектом и AI'
                        : canRead
                          ? 'Расшифровка готова'
                          : statuses[lecture?.status]}
                    </span>
                  </div>
                </div>
                <div className="heading-actions">
                  {demo ? (
                    <span className="enrolled-label">
                      <CheckCircle size={19} />
                      Открыто для знакомства
                    </span>
                  ) : (
                    course && (
                      <button
                        className={`enroll-button ${personal.is_enrolled_in_course ? 'enrolled-label' : ''}`}
                        disabled={actionBusy}
                        onClick={enrollment}
                      >
                        {personal.is_enrolled_in_course ? (
                          <CheckCircle size={18} />
                        ) : (
                          <Plus size={18} />
                        )}{' '}
                        {personal.is_enrolled_in_course
                          ? 'Вы записаны на курс'
                          : 'Записаться на курс'}
                      </button>
                    )
                  )}
                  <button
                    className="button primary share-button"
                    onClick={share}
                  >
                    <ShareNetwork size={19} />
                    <span>Поделиться</span>
                  </button>
                </div>
              </div>
            </section>
            <section className="learning-panel panel">
              {busy ? (
                <div className="loading-block">
                  <Spinner />
                  Готовим пространство для обучения…
                </div>
              ) : pageError ? (
                <>
                  <ErrorNotice error={pageError} />
                  <button
                    className="button secondary"
                    onClick={() => navigate('catalog')}
                  >
                    Вернуться в каталог
                  </button>
                </>
              ) : (
                <div className="learning-grid">
                  <div className="lesson-main">
                    <div
                      className={`video-wrap ${demo ? 'is-demo' : ''}`}
                      ref={videoWrap}
                    >
                      {demo ? (
                        <img
                          className="video-poster"
                          src="/assets/lecture-poster.png"
                          alt="Преподаватель рассказывает об основах дизайн-мышления"
                        />
                      ) : (
                        <video
                          ref={video}
                          src={lecture?.video_url || undefined}
                          preload="metadata"
                          muted={muted}
                          playsInline
                          onLoadedMetadata={() => {
                            if (seekTarget.current)
                              video.current.currentTime = Math.min(
                                seekTarget.current,
                                video.current.duration || Infinity,
                              );
                            video.current.playbackRate = speed;
                          }}
                          onTimeUpdate={() => {
                            setPosition(video.current.currentTime);
                            lastPositions.current[lectureId] =
                              video.current.currentTime;
                            seekTarget.current = video.current.currentTime;
                          }}
                          onPlay={() => setPlaying(true)}
                          onPause={() => {
                            setPlaying(false);
                            saveProgress(video.current?.currentTime || 0);
                          }}
                          onEnded={() => {
                            setPlaying(false);
                            saveProgress(
                              lecture.duration_seconds || position,
                              true,
                            );
                          }}
                          onError={() => setVideoError(true)}
                          onClick={togglePlay}
                          onDoubleClick={() =>
                            videoWrap.current?.requestFullscreen?.()
                          }
                        >
                          {lecture?.subtitles_url && (
                            <track
                              key={lectureId}
                              kind="subtitles"
                              src={lecture.subtitles_url}
                              srcLang={lecture.language || 'ru'}
                              label="Субтитры"
                            />
                          )}
                        </video>
                      )}
                      <div className="video-title">
                        <span>{lecture?.title}</span>
                        <button
                          className={`video-bookmark ${favorite ? 'selected' : ''}`}
                          onClick={toggleFavorite}
                          disabled={actionBusy}
                          aria-label={
                            favorite
                              ? 'Убрать из избранного'
                              : 'Добавить в избранное'
                          }
                        >
                          <BookmarkSimple
                            size={21}
                            weight={favorite ? 'fill' : 'regular'}
                          />
                        </button>
                      </div>
                      {demo && (
                        <button
                          className="center-play"
                          onClick={togglePlay}
                          aria-label="Смотреть демо-лекцию"
                        >
                          <Play size={25} weight="fill" />
                        </button>
                      )}
                      {!demo && (!lecture?.video_url || videoError) && (
                        <div className="video-unavailable">
                          <FileVideo size={36} weight="light" />
                          <strong>
                            {videoError
                              ? 'Не удалось воспроизвести видео'
                              : 'Видео готовится'}
                          </strong>
                          <p>
                            {videoError
                              ? 'Файл недоступен или его формат не поддерживается браузером.'
                              : 'Видео появится после скачивания и обработки.'}
                          </p>
                          {videoError && (
                            <button
                              className="button secondary"
                              onClick={() => {
                                setVideoError(false);
                                video.current?.load();
                              }}
                            >
                              Попробовать снова
                            </button>
                          )}
                        </div>
                      )}
                      <div className="video-controls">
                        <button
                          className="player-play"
                          onClick={togglePlay}
                          aria-label={playing ? 'Пауза' : 'Воспроизвести'}
                          disabled={!demo && !lecture?.video_url}
                        >
                          {playing ? (
                            <Pause size={20} weight="fill" />
                          ) : (
                            <Play size={20} weight="fill" />
                          )}
                        </button>
                        <span className="player-time">{time(position)}</span>
                        <input
                          aria-label="Позиция воспроизведения"
                          type="range"
                          min="0"
                          max={lecture?.duration_seconds || 1}
                          step="1"
                          value={Math.min(
                            position,
                            lecture?.duration_seconds || 1,
                          )}
                          onChange={(e) => seek(Number(e.target.value))}
                        />
                        <span className="player-time total-time">
                          {time(lecture?.duration_seconds)}
                        </span>
                        <button
                          className="player-icon volume-button"
                          onClick={() => setMuted(!muted)}
                          aria-label={
                            muted ? 'Включить звук' : 'Выключить звук'
                          }
                        >
                          {muted ? (
                            <SpeakerSlash size={20} />
                          ) : (
                            <SpeakerHigh size={20} />
                          )}
                        </button>
                        <select
                          aria-label="Скорость воспроизведения"
                          className="speed-select"
                          value={speed}
                          onChange={(e) => {
                            setSpeed(Number(e.target.value));
                            if (video.current)
                              video.current.playbackRate = Number(
                                e.target.value,
                              );
                          }}
                        >
                          {[0.75, 1, 1.25, 1.5, 2].map((n) => (
                            <option key={n} value={n}>
                              {n}×
                            </option>
                          ))}
                        </select>
                        {!demo && lecture?.subtitles_url && (
                          <button
                            className="player-icon"
                            aria-label="Включить или выключить субтитры"
                            onClick={() => {
                              const track = video.current?.textTracks[0];
                              if (track)
                                track.mode =
                                  track.mode === 'showing'
                                    ? 'hidden'
                                    : 'showing';
                            }}
                          >
                            CC
                          </button>
                        )}
                        <button
                          className="player-icon fullscreen-button"
                          aria-label="Полный экран"
                          onClick={() => {
                            if (document.fullscreenElement)
                              document.exitFullscreen();
                            else videoWrap.current?.requestFullscreen?.();
                          }}
                        >
                          <CornersOut size={22} />
                        </button>
                      </div>
                    </div>
                    {!demo &&
                      !['ready', 'failed'].includes(lecture?.status) && (
                        <div className="processing-card">
                          <Spinner />
                          <div>
                            <strong>{statuses[lecture?.status]}</strong>
                            <p>
                              Материал обрабатывается. Статус обновляется
                              автоматически.
                            </p>
                            <span>
                              Прогресс текущего этапа:{' '}
                              {Math.round((lecture?.progress || 0) * 100)}%
                            </span>
                          </div>
                        </div>
                      )}
                    {!demo && lecture?.status === 'failed' && (
                      <ErrorNotice
                        error={`Обработка не завершилась: ${lecture.error || 'неизвестная ошибка'}`}
                      />
                    )}
                    <div
                      className="lesson-tabs"
                      role="tablist"
                      aria-label="Материалы лекции"
                    >
                      {[
                        ['overview', 'Обзор'],
                        ['summary', 'Конспект'],
                        ['transcript', 'Расшифровка'],
                        ['terms', 'Термины'],
                        ['bookmarks', 'Мои заметки'],
                      ].map(([id, label]) => (
                        <button
                          role="tab"
                          aria-selected={tab === id}
                          className={tab === id ? 'active' : ''}
                          key={id}
                          onClick={() => setTab(id)}
                        >
                          {label}
                          {id === 'bookmarks' && bookmarks.length > 0 && (
                            <span className="tab-count">
                              {bookmarks.length}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                    <div className="lesson-content" role="tabpanel">
                      {tab === 'overview' && (
                        <>
                          <div className="about-heading">
                            <h2>
                              Об этой {demo || course ? 'программе' : 'лекции'}
                            </h2>
                            <span className="small-tag">
                              {demo
                                ? 'Начальный уровень'
                                : lecture?.language?.toUpperCase() || 'Видео'}
                            </span>
                          </div>
                          <p className="about-copy">
                            {demo
                              ? demoCourse.description
                              : course?.description ||
                                'Смотрите лекцию, изучайте конспект и задавайте вопросы AI-помощнику. Кликните по таймкоду в расшифровке, чтобы перейти к нужному моменту.'}
                          </p>
                          <h2 className="key-heading">
                            {demo
                              ? 'Чему вы научитесь'
                              : 'Всё для погружения в тему'}
                          </h2>
                          <div className="key-points">
                            {(demo
                              ? [
                                  'Понимать потребности пользователей',
                                  'Находить идеи и проверять гипотезы',
                                  'Структурировать сложные задачи',
                                  'Создавать и тестировать прототипы',
                                ]
                              : [
                                  'Находить фрагменты по смыслу',
                                  'Читать конспект с оглавлением',
                                  'Задавать вопросы по материалу',
                                  'Сохранять мысли на таймкодах',
                                ]
                            ).map((t) => (
                              <div key={t}>
                                <CheckCircle size={22} weight="light" />
                                <span>{t}</span>
                              </div>
                            ))}
                          </div>
                          <div className="instructor-row">
                            <span className="avatar instructor-avatar">
                              {demo ? (
                                <img
                                  src="/assets/lecture-poster.png"
                                  alt="Преподаватель"
                                />
                              ) : author?.avatar_url ? (
                                <img src={author.avatar_url} alt="" />
                              ) : (
                                <GraduationCap size={25} />
                              )}
                            </span>
                            <div>
                              <strong>
                                {demo
                                  ? 'Анна Смирнова'
                                  : author
                                    ? `${author.first_name} ${author.last_name}`
                                    : 'Команда Lectio'}
                              </strong>
                              <span>
                                {demo
                                  ? 'Демо-преподаватель · Product Designer'
                                  : 'Преподаватель'}
                              </span>
                            </div>
                            <button
                              className="text-button"
                              onClick={() => setModal('about-author')}
                            >
                              О преподавателе
                              <ArrowUpRight size={15} />
                            </button>
                          </div>
                        </>
                      )}
                      {tab === 'summary' && (
                        <>
                          <div className="content-heading">
                            <h2>Конспект лекции</h2>
                            <button
                              className="icon-button"
                              onClick={downloadSummary}
                              disabled={!summary?.summary}
                              aria-label="Скачать конспект"
                            >
                              <DownloadSimple size={20} />
                            </button>
                          </div>
                          {summary?.error && (
                            <ErrorNotice
                              error={`Конспект не удалось подготовить: ${summary.error}`}
                            />
                          )}
                          <div className="chapter-links">
                            {summary?.chapters?.map((c) => (
                              <React.Fragment key={c.id}>
                                <button onClick={() => seek(c.start_seconds)}>
                                  <span className="timecode">
                                    {time(c.start_seconds)}
                                  </span>
                                  {c.title}
                                  <ArrowUpRight size={14} />
                                </button>
                                {c.subsections?.map((s) => (
                                  <button
                                    className="subchapter"
                                    key={s.id}
                                    onClick={() => seek(s.start_seconds)}
                                  >
                                    <span className="timecode">
                                      {time(s.start_seconds)}
                                    </span>
                                    {s.title}
                                  </button>
                                ))}
                              </React.Fragment>
                            ))}
                          </div>
                          {summary?.summary ? (
                            <Markdown>{summary.summary}</Markdown>
                          ) : (
                            <Empty
                              icon={TextAlignLeft}
                              title="Конспект ещё не готов"
                            >
                              Он появится после обработки лекции. Расшифровка и
                              поиск могут быть доступны раньше.
                            </Empty>
                          )}
                        </>
                      )}
                      {tab === 'transcript' && (
                        <>
                          <div className="filter-input transcript-filter">
                            <MagnifyingGlass size={18} />
                            <input
                              placeholder="Найти в расшифровке…"
                              aria-label="Найти в расшифровке"
                              value={transcriptQuery}
                              onChange={(e) =>
                                setTranscriptQuery(e.target.value)
                              }
                            />
                          </div>
                          <div className="full-transcript">
                            {filteredSegments.map((s) => (
                              <button
                                key={s.id}
                                className={`transcript-row ${position >= s.start_seconds && position < s.end_seconds ? 'current' : ''}`}
                                onClick={() => seek(s.start_seconds)}
                              >
                                <span className="timecode">
                                  {time(s.start_seconds)}
                                </span>
                                <span>{s.text}</span>
                              </button>
                            ))}
                            {!filteredSegments.length && (
                              <Empty
                                title={
                                  segments.length
                                    ? 'Совпадений нет'
                                    : 'Расшифровка готовится'
                                }
                              >
                                {segments.length
                                  ? 'Попробуйте другие слова.'
                                  : 'Реплики появятся после распознавания речи.'}
                              </Empty>
                            )}
                          </div>
                        </>
                      )}
                      {tab === 'terms' && (
                        <>
                          <h2>Ключевые понятия</h2>
                          {summary?.key_terms?.length ? (
                            summary.key_terms.map((t) => (
                              <div className="term" key={t.term}>
                                <div>
                                  <strong>{t.term}</strong>
                                  {t.start_seconds != null && (
                                    <button
                                      className="timecode"
                                      onClick={() => seek(t.start_seconds)}
                                    >
                                      {time(t.start_seconds)}
                                      <ArrowUpRight size={13} />
                                    </button>
                                  )}
                                </div>
                                <p>{t.definition}</p>
                              </div>
                            ))
                          ) : (
                            <Empty
                              icon={BookOpenText}
                              title="Термины ещё не выделены"
                            >
                              Они появятся вместе с конспектом.
                            </Empty>
                          )}
                        </>
                      )}
                      {tab === 'bookmarks' && (
                        <>
                          <div className="content-heading">
                            <h2>Сохраните важную мысль</h2>
                            <span className="timecode">{time(position)}</span>
                          </div>
                          {demo && (
                            <p className="fine-print">
                              Демо-заметки сохраняются только в этом браузере.
                            </p>
                          )}
                          <form
                            className="bookmark-form"
                            onSubmit={addBookmark}
                          >
                            <textarea
                              maxLength={2000}
                              value={note}
                              onChange={(e) => setNote(e.target.value)}
                              placeholder="Что вы хотите запомнить?"
                              aria-label="Текст заметки"
                              rows={3}
                            />
                            <button
                              className="button primary"
                              disabled={actionBusy}
                            >
                              <Plus size={17} />
                              Добавить заметку
                            </button>
                          </form>
                          {bookmarks.map((b) => (
                            <div className="saved-note" key={b.id}>
                              <button
                                className="timecode"
                                onClick={() => seek(b.position_seconds)}
                              >
                                {time(b.position_seconds)}
                              </button>
                              <p>{b.note || 'Сохранённый момент'}</p>
                              <button
                                className="icon-button"
                                aria-label="Редактировать заметку"
                                onClick={() =>
                                  setModal({
                                    type: 'edit-bookmark',
                                    bookmark: b,
                                  })
                                }
                              >
                                <PencilSimple size={17} />
                              </button>
                              <button
                                className="icon-button danger"
                                aria-label="Удалить заметку"
                                disabled={actionBusy}
                                onClick={() => removeBookmark(b.id)}
                              >
                                <Trash size={17} />
                              </button>
                            </div>
                          ))}
                          {!bookmarks.length && (
                            <p className="muted bookmark-empty">
                              Здесь появятся ваши заметки с таймкодами.
                            </p>
                          )}
                        </>
                      )}
                    </div>
                    <div className="lesson-footer">
                      <button
                        className={`favorite-action ${favorite ? 'is-saved' : ''}`}
                        onClick={toggleFavorite}
                        disabled={actionBusy}
                      >
                        <BookmarkSimple
                          size={19}
                          weight={favorite ? 'fill' : 'regular'}
                        />
                        {favorite ? 'В избранном' : 'Сохранить лекцию'}
                      </button>
                      {!demo && user && (
                        <button
                          className="text-button"
                          onClick={() => {
                            saveProgress(
                              position,
                              !personal.progress?.completed,
                            );
                            notify(
                              personal.progress?.completed
                                ? 'Отметка завершения снята'
                                : 'Лекция отмечена завершённой',
                            );
                          }}
                        >
                          <CheckCircle size={19} />
                          {personal.progress?.completed
                            ? 'Пройдено'
                            : 'Завершить лекцию'}
                        </button>
                      )}
                      {personal.can_manage && (
                        <button
                          className="text-button"
                          onClick={() => setModal('manage')}
                        >
                          Управление
                          <DotsThree size={20} />
                        </button>
                      )}
                    </div>
                  </div>
                  <aside className="lesson-aside">
                    <div className="assistant-card">
                      <span className="ai-symbol">
                        <Lightning size={28} weight="light" />
                      </span>
                      <div>
                        <h2>
                          AI-помощник<span className="ai-label">AI</span>
                        </h2>
                        <p>
                          {chatBusy
                            ? 'Ищу ответ в лекции…'
                            : demo
                              ? 'Поможет разобраться в теме'
                              : 'Ответы по материалам лекции'}
                        </p>
                      </div>
                      <Waveform className="ai-wave" size={45} weight="light" />
                    </div>
                    <section className="aside-card notes-card">
                      <div
                        className="aside-tabs"
                        role="tablist"
                        aria-label="AI-помощник"
                      >
                        <button
                          role="tab"
                          aria-selected={rightTab === 'notes'}
                          className={rightTab === 'notes' ? 'active' : ''}
                          onClick={() => setRightTab('notes')}
                        >
                          <TextAlignLeft size={17} />
                          Важные моменты
                        </button>
                        <button
                          role="tab"
                          aria-selected={rightTab === 'chat'}
                          className={rightTab === 'chat' ? 'active' : ''}
                          onClick={() => setRightTab('chat')}
                        >
                          <ChatCircleDots size={17} />
                          Спросить AI
                        </button>
                      </div>
                      {rightTab === 'notes' ? (
                        <>
                          <div className="aside-section-title">
                            <h3>Заметки к лекции</h3>
                            <span className="ready-dot">
                              {canRead ? 'Готово' : 'В обработке'}
                            </span>
                          </div>
                          <div className="short-transcript">
                            {segments
                              .slice(demo ? 1 : 0, demo ? 6 : 8)
                              .map((s) => (
                                <button
                                  className={`note-row ${position >= s.start_seconds && position < s.end_seconds ? 'current' : ''}`}
                                  key={s.id}
                                  onClick={() => seek(s.start_seconds)}
                                >
                                  <span>{time(s.start_seconds)}</span>
                                  <p>{s.text}</p>
                                </button>
                              ))}
                            {!segments.length && (
                              <p className="muted small-empty">
                                Здесь появятся фрагменты расшифровки с
                                таймкодами.
                              </p>
                            )}
                          </div>
                          <button
                            className="view-all"
                            onClick={() => setTab('transcript')}
                          >
                            Вся расшифровка
                            <ArrowUpRight size={16} />
                          </button>
                        </>
                      ) : (
                        <div className="chat-panel">
                          <div className="chat-messages">
                            {!messages.length && (
                              <div className="chat-welcome">
                                <Lightning size={29} weight="light" />
                                <h3>Разберёмся вместе</h3>
                                <p>
                                  {demo
                                    ? 'Демо-ответы показывают, как устроен чат.'
                                    : 'Задайте вопрос — я найду ответ в этой лекции и покажу источник.'}
                                </p>
                                <button
                                  onClick={() =>
                                    ask(null, 'В чём главная мысль лекции?')
                                  }
                                >
                                  В чём главная мысль?
                                  <ArrowUpRight size={14} />
                                </button>
                                <button
                                  onClick={() =>
                                    ask(
                                      null,
                                      'Объясни основные понятия простыми словами',
                                    )
                                  }
                                >
                                  Объясни простыми словами
                                  <ArrowUpRight size={14} />
                                </button>
                              </div>
                            )}
                            {messages.map((m, i) => (
                              <div className="chat-exchange" key={i}>
                                <div className="chat-question">
                                  {m.question}
                                </div>
                                {m.answer && (
                                  <>
                                    <div className="chat-answer">
                                      <Lightning size={16} />
                                      <Markdown
                                        sources={m.sources}
                                        onSeek={(s) =>
                                          s.lecture_id === lectureId
                                            ? seek(s.start_seconds)
                                            : openLecture(
                                                s.lecture_id,
                                                s.start_seconds,
                                              )
                                        }
                                      >
                                        {m.answer}
                                      </Markdown>
                                    </div>
                                    <div className="chat-sources">
                                      {m.sources?.map((s, j) => (
                                        <button
                                          key={j}
                                          className="timecode"
                                          title={s.text}
                                          onClick={() =>
                                            s.lecture_id === lectureId
                                              ? seek(s.start_seconds)
                                              : openLecture(
                                                  s.lecture_id,
                                                  s.start_seconds,
                                                )
                                          }
                                        >
                                          [{j + 1}] {time(s.start_seconds)}
                                          <ArrowUpRight size={12} />
                                        </button>
                                      ))}
                                    </div>
                                  </>
                                )}
                              </div>
                            ))}
                            {chatBusy && (
                              <div className="chat-loading">
                                <Spinner />
                                Читаю лекцию и формирую ответ…
                                <button
                                  className="text-button"
                                  onClick={() => chatAbort.current?.abort()}
                                >
                                  Остановить
                                </button>
                              </div>
                            )}
                            <ErrorNotice error={chatError} />
                            <div ref={chatEnd} />
                          </div>
                          <form className="chat-input" onSubmit={ask}>
                            <input
                              value={question}
                              onChange={(e) => setQuestion(e.target.value)}
                              placeholder="Задайте вопрос по лекции…"
                              aria-label="Вопрос AI-помощнику"
                              maxLength={2000}
                              disabled={!canRead}
                            />
                            <button
                              className="icon-button"
                              aria-label="Отправить вопрос"
                              disabled={
                                chatBusy || !question.trim() || !canRead
                              }
                            >
                              <PaperPlaneTilt size={20} />
                            </button>
                          </form>
                        </div>
                      )}
                    </section>
                    <section className="aside-card playlist-card">
                      <div className="playlist-heading">
                        <h3>
                          {demo || course
                            ? 'Содержание курса'
                            : 'Другие лекции'}
                        </h3>
                        <span>{lectureCount(playlist.length)}</span>
                      </div>
                      {demo && (
                        <div className="playlist-progress">
                          <progress max="5" value="1" />
                          <span>Ваш следующий шаг к новым знаниям</span>
                        </div>
                      )}
                      <div className="playlist">
                        {playlist.map((l, i) => (
                          <button
                            className={`playlist-item ${l.id === lectureId ? 'active' : ''}`}
                            key={l.id}
                            onClick={() => openLecture(l.id)}
                          >
                            <span className="lesson-number">
                              {l.id === lectureId ? (
                                <Waveform size={18} />
                              ) : (
                                String(i + 1).padStart(2, '0')
                              )}
                            </span>
                            <span className="playlist-title">
                              <strong>{l.title}</strong>
                              <small>
                                {time(l.duration_seconds)}
                                {!['ready', 'summarizing'].includes(l.status) &&
                                  ` · ${statuses[l.status]}`}
                              </small>
                            </span>
                            <span className="playlist-play">
                              {l.id === lectureId ? (
                                <Play size={13} weight="fill" />
                              ) : (
                                <PlayCircle size={18} weight="light" />
                              )}
                            </span>
                          </button>
                        ))}
                      </div>
                      <div className="playlist-bottom">
                        <BookOpenText size={16} />
                        Учитесь в своём темпе
                      </div>
                    </section>
                    {demo && (
                      <button
                        className="real-library-link"
                        onClick={() => navigate('catalog')}
                      >
                        Перейти к настоящим лекциям
                        <ArrowUpRight size={17} />
                      </button>
                    )}
                  </aside>
                </div>
              )}
            </section>
          </>
        )}
        <footer className="main-footer">
          <span>
            Lectio<span className="footer-dot">·</span>Меньше рутины. Больше
            понимания.
          </span>
          <button onClick={() => setModal('help')}>
            Как это работает
            <ArrowUpRight size={13} />
          </button>
        </footer>
      </main>
      {modal === 'auth' && (
        <AuthModal
          onClose={() => setModal(null)}
          onSuccess={(u) => {
            setUser(u);
            notify(`Рады видеть вас, ${u.first_name}`);
            bump();
          }}
        />
      )}
      {(modal === 'search' || modal?.type === 'search') && (
        <SearchModal
          initialQuery={modal?.initialQuery || ''}
          onClose={() => setModal(null)}
          lecture={lecture}
          demo={demo}
          course={course}
          onOpen={openLecture}
        />
      )}
      {modal === 'upload' && user?.role === 'teacher' && (
        <UploadModal
          courses={courseOptions}
          onClose={() => setModal(null)}
          onCreated={(l, isCourse) => {
            bump();
            notify(
              isCourse
                ? 'Курс создан'
                : 'Лекция добавлена. Началась обработка.',
            );
            if (!isCourse) openLecture(l.id);
          }}
        />
      )}
      {modal === 'profile' && user && (
        <ProfileModal
          user={user}
          onClose={() => setModal(null)}
          onChange={setUser}
          onLogout={logout}
        />
      )}
      {modal === 'demo-video' && (
        <Modal
          title="От знакомства — к знаниям"
          subtitle="Сейчас открыт демонстрационный курс с примером конспекта и расшифровки."
          onClose={() => setModal(null)}
        >
          <div className="demo-explanation">
            <PlayCircle size={42} weight="light" />
            <p>
              В демо-курсе нет видео. Откройте материал из библиотеки, чтобы
              смотреть настоящую лекцию, искать по её содержимому и задавать
              вопросы AI.
            </p>
            <button
              className="button primary"
              onClick={() => {
                setModal(null);
                navigate('catalog');
              }}
            >
              Открыть библиотеку
              <ArrowRight size={18} />
            </button>
          </div>
        </Modal>
      )}
      {modal === 'help' && (
        <Modal
          title="Знания без лишней рутины"
          subtitle="Lectio помогает не просто смотреть, а понимать."
          onClose={() => setModal(null)}
        >
          <div className="help-steps">
            {[
              [
                PlayCircle,
                'Смотрите в своём темпе',
                'Откройте лекцию. Войдите в аккаунт, чтобы сохранять позицию просмотра.',
              ],
              [
                MagnifyingGlass,
                'Находите по смыслу',
                'Поиск покажет фрагменты с таймкодами. Клик — и вы в нужном моменте.',
              ],
              [
                Lightning,
                'Спрашивайте и разбирайтесь',
                'AI отвечает по материалу лекции и указывает источники.',
              ],
              [
                BookmarkSimple,
                'Возвращайтесь к важному',
                'Сохраняйте лекции, пишите заметки и скачивайте конспекты.',
              ],
            ].map(([Icon, title, text]) => (
              <div key={title}>
                <Icon size={25} weight="light" />
                <div>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </div>
              </div>
            ))}
          </div>
        </Modal>
      )}
      {modal === 'about-author' && (
        <Modal
          title={
            demo
              ? 'Анна Смирнова'
              : author
                ? `${author.first_name} ${author.last_name}`
                : 'Преподаватель'
          }
          onClose={() => setModal(null)}
        >
          <p className="about-copy">
            {demo
              ? 'Пример профиля преподавателя для демонстрационного курса «Основы дизайн-мышления». Для настоящих лекций имя и аватар загружаются с сервера.'
              : 'Преподаватель и автор учебных материалов. Все доступные лекции можно найти в каталоге.'}
          </p>
          <button
            className="button secondary"
            onClick={() => {
              setModal(null);
              navigate('catalog');
            }}
          >
            Перейти к лекциям
            <ArrowRight size={17} />
          </button>
        </Modal>
      )}
      {modal === 'manage' && personal.can_manage && (
        <ManageModal
          lecture={lecture}
          courses={courseOptions}
          onClose={() => setModal(null)}
          onUpdated={() => {
            setModal(null);
            setLectureRevision((r) => r + 1);
            bump();
          }}
          onDeleted={() => {
            setModal(null);
            navigate('catalog');
            bump();
          }}
          notify={notify}
        />
      )}
      {modal?.type === 'edit-bookmark' && (
        <EditBookmarkModal
          bookmark={modal.bookmark}
          demo={modal.demo ?? demo}
          onClose={() => setModal(null)}
          onSaved={(b) => {
            if (modal.demo ?? demo)
              setDemoSaved((s) => ({
                ...s,
                bookmarks: (s.bookmarks || []).map((x) =>
                  x.id === b.id ? b : x,
                ),
              }));
            else bump();
            setModal(null);
            notify('Заметка обновлена');
          }}
        />
      )}
      {modal?.type === 'share' && (
        <Modal title="Ссылка на этот момент" onClose={() => setModal(null)}>
          <input
            className="share-url"
            value={modal.url}
            readOnly
            onFocus={(e) => e.target.select()}
          />
          <p className="fine-print">
            Скопируйте ссылку. Локальный адрес доступен только на этом
            компьютере.
          </p>
        </Modal>
      )}
      {toast && (
        <div className="toast" role="status">
          <CheckCircle size={19} />
          {toast}
          <button
            onClick={() => setToast(null)}
            aria-label="Закрыть уведомление"
          >
            <X size={16} />
          </button>
        </div>
      )}
      <KeyboardShortcut onSearch={() => setModal('search')} />
    </div>
  );
}

function KeyboardShortcut({ onSearch }) {
  useEffect(() => {
    function key(e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        onSearch();
      }
    }
    document.addEventListener('keydown', key);
    return () => document.removeEventListener('keydown', key);
  }, [onSearch]);
  return null;
}
function EditBookmarkModal({ bookmark, demo, onClose, onSaved }) {
  const [error, setError] = useState(null),
    [busy, setBusy] = useState(false);
  return (
    <Modal title="Редактировать заметку" onClose={onClose}>
      <form
        className="form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          const f = new FormData(e.currentTarget);
          const body = {
            note: f.get('note') || null,
            position_seconds: Number(f.get('position_seconds')),
          };
          try {
            onSaved(
              demo
                ? { ...bookmark, ...body }
                : await api(`/bookmarks/${bookmark.id}`, {
                    method: 'PATCH',
                    body,
                  }),
            );
          } catch (err) {
            setError(err);
          } finally {
            setBusy(false);
          }
        }}
      >
        <ErrorNotice error={error} />
        <label>
          Таймкод в секундах
          <input
            type="number"
            min="0"
            step="0.1"
            name="position_seconds"
            defaultValue={bookmark.position_seconds}
            required
          />
        </label>
        <label>
          Заметка
          <textarea
            name="note"
            maxLength={2000}
            defaultValue={bookmark.note || ''}
            rows={4}
          />
        </label>
        <button className="button primary" disabled={busy}>
          {busy ? <Spinner /> : <Check size={17} />}Сохранить
        </button>
      </form>
    </Modal>
  );
}
function ManageModal({
  lecture,
  courses,
  onClose,
  onUpdated,
  onDeleted,
  notify,
}) {
  const [error, setError] = useState(null),
    [busy, setBusy] = useState(false),
    [confirmDelete, setConfirmDelete] = useState(false);
  async function action(path, method = 'POST') {
    setBusy(true);
    setError(null);
    try {
      await api(path, { method });
      notify('Запрос принят. Обработка выполняется в фоне.');
      onUpdated();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Управление лекцией" onClose={onClose}>
      <form
        className="form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          const f = new FormData(e.currentTarget);
          try {
            await api(`/lectures/${lecture.id}`, {
              method: 'PATCH',
              body: {
                title: f.get('title'),
                course_id: f.get('course_id') || null,
              },
            });
            onUpdated();
          } catch (err) {
            setError(err);
          } finally {
            setBusy(false);
          }
        }}
      >
        <ErrorNotice error={error} />
        <label>
          Название
          <input
            name="title"
            defaultValue={lecture.title}
            required
            maxLength={300}
          />
        </label>
        <label>
          Курс
          <select name="course_id" defaultValue={lecture.course_id || ''}>
            <option value="">Без курса</option>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </label>
        <button className="button primary" disabled={busy}>
          Сохранить изменения
        </button>
      </form>
      <div className="manage-actions">
        <button
          className="button secondary"
          disabled={busy || lecture.status !== 'ready'}
          onClick={() => action(`/lectures/${lecture.id}/summary`)}
        >
          <ArrowClockwise size={17} />
          Обновить конспект
        </button>
        <p className="fine-print">
          Запрос создаёт фоновую задачу. Старый конспект остаётся видимым до
          обновления; обновите страницу позже.
        </p>
        <button
          className="button secondary"
          disabled={busy || !['ready', 'failed'].includes(lecture.status)}
          onClick={() => action(`/lectures/${lecture.id}/reprocess`)}
        >
          <ArrowClockwise size={17} />
          Обработать заново
        </button>
      </div>
      <div className="delete-zone">
        {confirmDelete ? (
          <>
            <p>
              Удалить лекцию, её файлы и связанные заметки? Это действие нельзя
              отменить.
            </p>
            <button
              className="button danger-button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await api(`/lectures/${lecture.id}`, { method: 'DELETE' });
                  onDeleted();
                } catch (err) {
                  setError(err);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Удалить навсегда
            </button>
            <button
              className="text-button"
              onClick={() => setConfirmDelete(false)}
            >
              Отмена
            </button>
          </>
        ) : (
          <button
            className="text-button danger"
            onClick={() => setConfirmDelete(true)}
          >
            <Trash size={17} />
            Удалить лекцию
          </button>
        )}
      </div>
    </Modal>
  );
}

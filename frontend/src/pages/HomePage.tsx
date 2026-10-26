import { ArrowRight, BookMarked, CheckCircle2, Clock, Compass, History, PlayCircle, Search } from 'lucide-react';
import { type FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router';

import { useCourses, useDashboard, useLectures, useMyCourses } from '../api/hooks';
import { useAuth } from '../auth/AuthProvider';
import { CourseCard } from '../components/CourseCard';
import { LectureCard } from '../components/LectureCard';
import { Empty, Skeleton } from '../components/ui';

const HINTS = ['объяснение теоремы Пифагора', 'что такое производная', 'пример с площадями'];

function Hero({ name }: { name?: string }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  const go = (text: string) => navigate(`/search?q=${encodeURIComponent(text)}`);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (query.trim()) go(query.trim());
  };

  return (
    <section className="card hero">
      <div className="eyebrow" style={{ color: 'rgb(255 255 255 / 0.6)' }}>
        {name ? `С возвращением, ${name}` : 'Смысловой поиск по видеолекциям'}
      </div>
      <h1>Найдите нужный момент в любой лекции — по смыслу, а не по словам</h1>
      <p>Lectio расшифровывает видео, строит конспект с оглавлением и отвечает на вопросы со ссылками на таймкоды.</p>
      <form className="hero-search" onSubmit={submit}>
        <input
          className="input"
          placeholder="Что вы хотите найти?"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn">
          <Search size={17} /> Найти
        </button>
      </form>
      <div className="hero-hints">
        {HINTS.map((hint) => (
          <button key={hint} type="button" onClick={() => go(hint)}>
            {hint}
          </button>
        ))}
      </div>
    </section>
  );
}

function Stat({ icon, value, label }: { icon: React.ReactNode; value: string | number; label: string }) {
  return (
    <div className="card stat">
      <span className="stat-icon">{icon}</span>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

function SectionHead({ title, to, label = 'Смотреть все' }: { title: string; to?: string; label?: string }) {
  return (
    <div className="card-head">
      <h2>{title}</h2>
      {to && (
        <Link to={to} className="btn btn-ghost btn-sm">
          {label} <ArrowRight size={14} />
        </Link>
      )}
    </div>
  );
}

function Dashboard() {
  const { user } = useAuth();
  const { data: dashboard } = useDashboard();
  const { data: myCourses } = useMyCourses();
  const { data: recent = [] } = useLectures();
  const navigate = useNavigate();

  const hours = (dashboard?.watched_seconds ?? 0) / 3600;

  return (
    <div className="page">
      <Hero name={user?.first_name} />

      <div className="stats">
        <Stat icon={<CheckCircle2 size={18} />} value={dashboard?.lectures_completed ?? '—'} label="лекций просмотрено" />
        <Stat icon={<PlayCircle size={18} />} value={dashboard?.lectures_in_progress ?? '—'} label="в процессе" />
        <Stat
          icon={<Clock size={18} />}
          value={
            !dashboard
              ? '—'
              : hours >= 1
                ? `${hours.toFixed(1)} ч`
                : dashboard.watched_seconds < 60
                  ? '< 1 мин'
                  : `${Math.round(hours * 60)} мин`
          }
          label="времени в лекциях"
        />
        <Stat icon={<BookMarked size={18} />} value={dashboard?.bookmarks ?? '—'} label="заметок на таймкодах" />
      </div>

      {!!dashboard?.continue_watching.length && (
        <section className="card card-pad">
          <SectionHead title="Продолжить просмотр" />
          <div className="grid">
            {dashboard.continue_watching.map((item) => (
              <LectureCard key={item.lecture.id} lecture={item.lecture} watched={item.position_seconds} />
            ))}
          </div>
        </section>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 2fr) minmax(0, 1fr)', gap: 16 }} className="home-split">
        <section className="card card-pad">
          <SectionHead title="Мои курсы" to="/courses" label="Все курсы" />
          {myCourses?.length ? (
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))' }}>
              {myCourses.slice(0, 4).map((course) => (
                <CourseCard key={course.id} course={course} />
              ))}
            </div>
          ) : (
            <Empty
              icon={<Compass size={22} />}
              title="Вы ещё не записались на курсы"
              action={
                <Link to="/courses" className="btn btn-sm">
                  Выбрать курс
                </Link>
              }
            >
              Запишитесь, чтобы видеть прогресс прохождения.
            </Empty>
          )}
        </section>

        <section className="card card-pad">
          <SectionHead title="Недавние поиски" />
          {dashboard?.recent_searches.length ? (
            <div className="chips">
              {dashboard.recent_searches.map((item) => (
                <button
                  key={item.query}
                  className="chip"
                  onClick={() => navigate(`/search?q=${encodeURIComponent(item.query)}`)}
                >
                  <History size={13} /> {item.query}
                </button>
              ))}
            </div>
          ) : (
            <p className="muted" style={{ fontSize: 14 }}>Здесь появятся ваши запросы.</p>
          )}
        </section>
      </div>

      <section className="card card-pad">
        <SectionHead title="Новые лекции" to="/lectures" />
        <div className="grid">
          {recent.slice(0, 4).map((lecture) => (
            <LectureCard key={lecture.id} lecture={lecture} />
          ))}
        </div>
      </section>
    </div>
  );
}

function Welcome() {
  const { data: lectures, isLoading } = useLectures();
  const { data: courses = [] } = useCourses();

  return (
    <div className="page">
      <Hero />

      {courses.length > 0 && (
        <section className="card card-pad">
          <SectionHead title="Курсы" to="/courses" />
          <div className="grid">
            {courses.slice(0, 3).map((course) => (
              <CourseCard key={course.id} course={course} />
            ))}
          </div>
        </section>
      )}

      <section className="card card-pad">
        <SectionHead title="Новые лекции" to="/lectures" />
        {isLoading ? (
          <div className="grid">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} height={240} />
            ))}
          </div>
        ) : (
          <div className="grid">
            {lectures?.slice(0, 6).map((lecture) => (
              <LectureCard key={lecture.id} lecture={lecture} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

export function HomePage() {
  const { user } = useAuth();
  return user ? <Dashboard /> : <Welcome />;
}

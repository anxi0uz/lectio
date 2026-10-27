import { ArrowRight, Compass } from 'lucide-react';
import { type FormEvent, useState } from 'react';
import { Link, useNavigate } from 'react-router';

import { useCourses, useDashboard, useLectures, useMyAchievements, useMyCourses } from '../api/hooks';
import { useAuth } from '../auth/AuthProvider';
import { CourseCard } from '../components/CourseCard';
import { LevelBar, achievementsCount } from '../components/Gamification';
import { LectureCard } from '../components/LectureCard';
import { Empty, Skeleton } from '../components/ui';

const HINTS = ['объяснение теоремы Пифагора', 'как учиться с помощью AI', 'зачем строить квадрат a + b'];

function Hero({ name }: { name?: string }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  const go = (text: string) => navigate(`/search?q=${encodeURIComponent(text)}`);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (query.trim()) go(query.trim());
  };

  return (
    <section className="hero">
      <div className="eyebrow">
        <span>{name ? `С возвращением, ${name}` : 'Смысловой поиск по видеолекциям'}</span>
      </div>
      <h1>
        Найдите нужный момент в любой лекции — <span className="accent">по смыслу</span>, а не по словам
      </h1>
      <p>Lectio расшифровывает видео, строит конспект с оглавлением и отвечает на вопросы со ссылками на таймкоды.</p>
      <form className="hero-search" onSubmit={submit} role="search">
        <input
          placeholder="Что вы хотите найти?"
          aria-label="Поиск по лекциям"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn btn-accent">Найти</button>
      </form>
      <div className="hero-hints">
        <span className="muted">НАПРИМЕР:</span>
        {HINTS.map((hint) => (
          <button key={hint} type="button" onClick={() => go(hint)}>
            {hint}
          </button>
        ))}
      </div>
    </section>
  );
}

function SectionHead({ title, to, label = 'Все' }: { title: string; to?: string; label?: string }) {
  return (
    <div className="card-head">
      <h2>{title}</h2>
      {to && (
        <Link to={to} className="link" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          {label} <ArrowRight size={15} />
        </Link>
      )}
    </div>
  );
}

function watchedTime(seconds: number) {
  const hours = seconds / 3600;
  if (hours >= 1) return `${hours.toFixed(1)} ч`;
  if (seconds < 60) return '< 1 мин';
  return `${Math.round(seconds / 60)} мин`;
}

function Dashboard() {
  const { user } = useAuth();
  const { data: dashboard } = useDashboard();
  const { data: achievements } = useMyAchievements();
  const { data: myCourses } = useMyCourses();
  const { data: recent = [] } = useLectures();
  const navigate = useNavigate();

  return (
    <div className="page">
      <Hero name={user?.first_name} />

      <div className="stats">
        <div className="stat">
          <span className="stat-value">{dashboard?.lectures_completed ?? '—'}</span>
          <span className="stat-label">лекций просмотрено</span>
        </div>
        <div className="stat">
          <span className="stat-value">{dashboard?.lectures_in_progress ?? '—'}</span>
          <span className="stat-label">в процессе</span>
        </div>
        <div className="stat">
          <span className="stat-value accent">{dashboard ? watchedTime(dashboard.watched_seconds) : '—'}</span>
          <span className="stat-label">времени в лекциях</span>
        </div>
        <div className="stat">
          <span className="stat-value">{dashboard?.bookmarks ?? '—'}</span>
          <span className="stat-label">заметок на таймкодах</span>
        </div>
      </div>

      {achievements && (
        <Link to="/leaderboard" className="home-level">
          <LevelBar level={achievements.level} />
          <span className="home-level-link">
            {achievementsCount(achievements.achievements.filter((item) => item.unlocked).length)} · рейтинг →
          </span>
        </Link>
      )}

      {!!dashboard?.continue_watching.length && (
        <section className="card-pad">
          <SectionHead title="Продолжить просмотр" />
          <div className="grid">
            {dashboard.continue_watching.map((item) => (
              <LectureCard key={item.lecture.id} lecture={item.lecture} watched={item.position_seconds} />
            ))}
          </div>
        </section>
      )}

      <div className="card home-split card-pad">
        <section>
          <SectionHead title="Мои курсы" to="/courses" label="Все курсы" />
          {myCourses?.length ? (
            myCourses.slice(0, 4).map((course, index) => <CourseCard key={course.id} course={course} index={index} />)
          ) : (
            <Empty
              icon={<Compass size={24} />}
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

        <section>
          <SectionHead title="Недавние поиски" />
          {dashboard?.recent_searches.length ? (
            <div className="chips">
              {dashboard.recent_searches.map((item) => (
                <button
                  key={item.query}
                  className="chip"
                  onClick={() => navigate(`/search?q=${encodeURIComponent(item.query)}`)}
                >
                  {item.query}
                </button>
              ))}
            </div>
          ) : (
            <p className="muted">Здесь появятся ваши запросы.</p>
          )}
        </section>
      </div>

      <section className="card card-pad">
        <SectionHead title="Новые лекции" to="/lectures" label="Все лекции" />
        <div className="grid">
          {recent.slice(0, 3).map((lecture) => (
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

      <section className="card card-pad">
        <SectionHead title="Новые лекции" to="/lectures" label="Все лекции" />
        {isLoading ? (
          <div className="grid">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} height={260} />
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

      {courses.length > 0 && (
        <section className="card card-pad">
          <SectionHead title="Курсы" to="/courses" label="Все курсы" />
          {courses.slice(0, 4).map((course, index) => (
            <CourseCard key={course.id} course={course} index={index} />
          ))}
        </section>
      )}
    </div>
  );
}

export function HomePage() {
  const { user } = useAuth();
  return user ? <Dashboard /> : <Welcome />;
}

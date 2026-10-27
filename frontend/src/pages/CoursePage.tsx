import { BookOpen, CheckCircle2, Search, Upload } from 'lucide-react';
import { type FormEvent, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';

import { useCourse, useEnrollment, useLectures, useMyCourses } from '../api/hooks';
import { useAuth } from '../auth/AuthProvider';
import { LectureCard } from '../components/LectureCard';
import { Bar, Empty, Skeleton } from '../components/ui';
import { duration, lectures as lecturesLabel } from '../lib/format';

export function CoursePage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { user, isTeacher } = useAuth();
  const { data: course, isError } = useCourse(id);
  const { data: lectures = [], isLoading } = useLectures({ courseId: id });
  const { data: mine = [] } = useMyCourses();
  const enrollment = useEnrollment(id);
  const [query, setQuery] = useState('');

  const enrolled = mine.find((item) => item.id === id);
  const canUpload = isTeacher && course && (!course.owner_id || course.owner_id === user?.id);

  if (isError) {
    return (
      <div className="card">
        <Empty icon={<BookOpen size={22} />} title="Курс не найден" />
      </div>
    );
  }

  const search = (event: FormEvent) => {
    event.preventDefault();
    if (query.trim()) navigate(`/search?q=${encodeURIComponent(query.trim())}&course=${id}`);
  };

  return (
    <div className="page">
      <section className="page-header">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="eyebrow">
            <Link to="/courses">Курс</Link>
            {course && <span className="accent">{lecturesLabel(course.lectures_count)} · {duration(course.total_duration_seconds)}</span>}
          </div>
          {course ? <h1>{course.title}</h1> : <Skeleton width="50%" height={32} />}
          {course?.description && <p>{course.description}</p>}
          {enrolled && (
            <div style={{ marginTop: 16, maxWidth: 360, display: 'flex', flexDirection: 'column', gap: 6 }}>
              <Bar value={enrolled.progress} brand />
              <span className="muted" style={{ fontSize: 13 }}>
                Пройдено {enrolled.completed_lectures} из {enrolled.lectures_count}
              </span>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {canUpload && (
            <Link to={`/upload?course=${id}`} className="btn">
              <Upload size={16} /> Добавить лекцию
            </Link>
          )}
          {user &&
            (enrolled ? (
              <button className="btn" onClick={() => enrollment.leave.mutate()} disabled={enrollment.leave.isPending}>
                <CheckCircle2 size={16} /> Вы записаны
              </button>
            ) : (
              <button className="btn btn-primary" onClick={() => enrollment.enroll.mutate()} disabled={enrollment.enroll.isPending}>
                Записаться на курс
              </button>
            ))}
          {!user && (
            <Link to="/login" className="btn btn-primary">
              Войти и записаться
            </Link>
          )}
        </div>
      </section>

      <section className="card card-pad">
        <form onSubmit={search} style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={16} className="muted" style={{ position: 'absolute', left: 12, top: 13 }} />
            <input
              className="input"
              style={{ paddingLeft: 36 }}
              placeholder="Поиск по всем лекциям курса"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <button className="btn" disabled={!query.trim()}>
            Найти
          </button>
        </form>

        {isLoading ? (
          <div className="grid">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} height={240} />
            ))}
          </div>
        ) : lectures.length ? (
          <div className="grid">
            {[...lectures].reverse().map((lecture) => (
              <LectureCard key={lecture.id} lecture={lecture} />
            ))}
          </div>
        ) : (
          <Empty icon={<BookOpen size={22} />} title="В курсе пока нет лекций" />
        )}
      </section>
    </div>
  );
}

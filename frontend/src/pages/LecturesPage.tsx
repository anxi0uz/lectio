import { Compass, Search, Upload } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router';

import { useCourses, useLectures } from '../api/hooks';
import { useAuth } from '../auth/AuthProvider';
import { LectureCard } from '../components/LectureCard';
import { Empty, Skeleton } from '../components/ui';
import { lectures as lecturesLabel } from '../lib/format';

export function LecturesPage() {
  const { isTeacher, user } = useAuth();
  const [courseId, setCourseId] = useState('');
  const [mine, setMine] = useState(false);
  const [filter, setFilter] = useState('');

  const { data: lectures, isLoading } = useLectures({
    courseId: courseId || undefined,
    ownerId: mine ? user?.id : undefined,
  });
  const { data: courses = [] } = useCourses();
  const courseTitles = useMemo(() => new Map(courses.map((c) => [c.id, c.title])), [courses]);

  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return (lectures ?? []).filter((lecture) => lecture.title.toLowerCase().includes(needle));
  }, [lectures, filter]);

  return (
    <div className="page">
      <section className="card page-header">
        <div>
          <div className="eyebrow">Библиотека</div>
          <h1>Все лекции</h1>
          <p>{lectures ? lecturesLabel(lectures.length) : 'Загружаем…'} — с расшифровкой, конспектом и поиском по смыслу.</p>
        </div>
        {isTeacher && (
          <Link to="/upload" className="btn btn-primary">
            <Upload size={16} /> Загрузить лекцию
          </Link>
        )}
      </section>

      <section className="card card-pad">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 20 }}>
          <div style={{ position: 'relative', flex: '1 1 260px' }}>
            <Search size={16} className="muted" style={{ position: 'absolute', left: 12, top: 13 }} />
            <input
              className="input"
              style={{ paddingLeft: 36 }}
              placeholder="Фильтр по названию"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          <select className="select" style={{ flex: '0 1 240px' }} value={courseId} onChange={(e) => setCourseId(e.target.value)}>
            <option value="">Все курсы</option>
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.title}
              </option>
            ))}
          </select>
          {isTeacher && (
            <div className="segmented">
              <button className={!mine ? 'active' : ''} onClick={() => setMine(false)}>
                Все
              </button>
              <button className={mine ? 'active' : ''} onClick={() => setMine(true)}>
                Мои
              </button>
            </div>
          )}
        </div>

        {isLoading ? (
          <div className="grid">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} height={240} />
            ))}
          </div>
        ) : visible.length ? (
          <div className="grid">
            {visible.map((lecture) => (
              <LectureCard
                key={lecture.id}
                lecture={lecture}
                courseTitle={lecture.course_id ? courseTitles.get(lecture.course_id) : undefined}
              />
            ))}
          </div>
        ) : (
          <Empty icon={<Compass size={22} />} title="Лекций не нашлось">
            {filter ? 'Попробуйте другое название.' : 'Здесь появятся загруженные лекции.'}
          </Empty>
        )}
      </section>
    </div>
  );
}

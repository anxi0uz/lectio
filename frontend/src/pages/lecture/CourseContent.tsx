import { Link } from 'react-router';

import { useLectures } from '../../api/hooks';
import type { Course } from '../../api/types';
import { StatusBadge } from '../../components/ui';
import { lectures as lecturesLabel, timecode } from '../../lib/format';

export function CourseContent({ course, currentId }: { course: Course; currentId: string }) {
  const { data: lectures = [] } = useLectures({ courseId: course.id });
  // Oldest first reads as the course order.
  const ordered = [...lectures].reverse();

  return (
    <section aria-label="Содержание курса">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
        <h2 className="label">Курс · {course.title}</h2>
        <span className="label muted">{lecturesLabel(ordered.length)}</span>
      </div>
      {ordered.map((lecture, index) => (
        <Link
          key={lecture.id}
          to={`/lectures/${lecture.id}`}
          className={`course-item${lecture.id === currentId ? ' current' : ''}`}
          aria-current={lecture.id === currentId ? 'page' : undefined}
        >
          <span className="course-item-index">{String(index + 1).padStart(2, '0')}</span>
          <span className="course-item-title">{lecture.title}</span>
          <span className="course-item-meta">
            {lecture.status === 'ready' ? timecode(lecture.duration_seconds) : <StatusBadge status={lecture.status} />}
          </span>
        </Link>
      ))}
    </section>
  );
}

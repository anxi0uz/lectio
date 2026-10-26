import { Pause, Play } from 'lucide-react';
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
    <div className="panel">
      <div className="panel-head">
        <h3>Содержание курса</h3>
        <span className="muted" style={{ fontSize: 13 }}>{lecturesLabel(ordered.length)}</span>
      </div>
      <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 420, overflowY: 'auto' }}>
        {ordered.map((lecture, index) => {
          const current = lecture.id === currentId;

          return (
            <Link key={lecture.id} to={`/lectures/${lecture.id}`} className={`course-item${current ? ' current' : ''}`}>
              <span className="course-item-index">{String(index + 1).padStart(2, '0')}</span>
              <div style={{ minWidth: 0 }}>
                <div className="course-item-title">{lecture.title}</div>
                <div className="course-item-meta">
                  {lecture.status === 'ready' ? timecode(lecture.duration_seconds) : <StatusBadge status={lecture.status} />}
                </div>
              </div>
              <span className="course-item-icon">{current ? <Pause size={13} /> : <Play size={13} />}</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

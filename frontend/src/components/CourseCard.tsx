import { Link } from 'react-router';

import type { Course, EnrolledCourse } from '../api/types';
import { duration, lectures } from '../lib/format';
import { Bar } from './ui';

export function CourseCard({ course, index }: { course: Course | EnrolledCourse; index: number }) {
  const enrolled = 'progress' in course ? course : null;

  return (
    <Link to={`/courses/${course.id}`} className="course-card">
      <span className="course-num">{String(index + 1).padStart(2, '0')}</span>
      <div style={{ minWidth: 0 }}>
        <div className="course-card-title">{course.title}</div>
        {course.description && <p className="course-card-desc">{course.description}</p>}
        <div className="meta-row" style={{ marginTop: 12 }}>
          <span>{lectures(course.lectures_count).toUpperCase()}</span>
          <span>{duration(course.total_duration_seconds).toUpperCase()}</span>
          {enrolled && (
            <span className="accent">
              {enrolled.progress >= 1 ? 'ПРОЙДЕН' : `ПРОЙДЕНО ${enrolled.completed_lectures} ИЗ ${course.lectures_count}`}
            </span>
          )}
        </div>
        {enrolled && (
          <div style={{ marginTop: 12, maxWidth: 360 }}>
            <Bar value={enrolled.progress} brand />
          </div>
        )}
      </div>
    </Link>
  );
}

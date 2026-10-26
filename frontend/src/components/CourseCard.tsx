import { BookOpen, Check } from 'lucide-react';
import { Link } from 'react-router';

import type { Course, EnrolledCourse } from '../api/types';
import { duration, lectures } from '../lib/format';
import { Bar } from './ui';

export function CourseCard({ course }: { course: Course | EnrolledCourse }) {
  const enrolled = 'progress' in course ? course : null;

  return (
    <Link to={`/courses/${course.id}`} className="card course-card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span className="course-icon">
          <BookOpen size={20} />
        </span>
        {enrolled && enrolled.progress >= 1 && (
          <span className="badge badge-success">
            <Check size={12} /> Пройден
          </span>
        )}
      </div>
      <div>
        <div className="course-card-title">{course.title}</div>
        {course.description && <p className="course-card-desc" style={{ marginTop: 6 }}>{course.description}</p>}
      </div>
      <div className="meta-row" style={{ marginTop: 'auto' }}>
        <span>{lectures(course.lectures_count)}</span>
        <span>{duration(course.total_duration_seconds)}</span>
      </div>
      {enrolled && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Bar value={enrolled.progress} brand />
          <span className="muted" style={{ fontSize: 12 }}>
            Просмотрено {enrolled.completed_lectures} из {course.lectures_count}
          </span>
        </div>
      )}
    </Link>
  );
}

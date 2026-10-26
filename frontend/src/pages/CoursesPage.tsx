import { Library, Plus } from 'lucide-react';
import { type FormEvent, useState } from 'react';
import { useNavigate } from 'react-router';

import { useCourses, useCreateCourse, useMyCourses } from '../api/hooks';
import { useAuth } from '../auth/AuthProvider';
import { CourseCard } from '../components/CourseCard';
import { Empty, Modal, Skeleton, useToast } from '../components/ui';

function CreateCourseModal({ onClose }: { onClose: () => void }) {
  const create = useCreateCourse();
  const navigate = useNavigate();
  const toast = useToast();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(
      { title: title.trim(), description: description.trim() || undefined },
      {
        onSuccess: (course) => {
          toast('Курс создан');
          navigate(`/courses/${course.id}`);
        },
      },
    );
  };

  return (
    <Modal title="Новый курс" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        {create.error && <div className="alert alert-error">{create.error.message}</div>}
        <div className="field">
          <label htmlFor="course-title">Название</label>
          <input id="course-title" className="input" required value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
        </div>
        <div className="field">
          <label htmlFor="course-description">Описание</label>
          <textarea
            id="course-description"
            className="textarea"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        <button className="btn btn-primary" disabled={!title.trim() || create.isPending}>
          Создать курс
        </button>
      </form>
    </Modal>
  );
}

export function CoursesPage() {
  const { isTeacher, user } = useAuth();
  const { data: courses, isLoading } = useCourses();
  const { data: mine = [] } = useMyCourses();
  const [creating, setCreating] = useState(false);
  const enrolled = new Map(mine.map((course) => [course.id, course]));

  return (
    <div className="page">
      <section className="card page-header">
        <div>
          <div className="eyebrow">Каталог</div>
          <h1>Курсы</h1>
          <p>Лекции, собранные в программы. Запишитесь, чтобы видеть свой прогресс.</p>
        </div>
        {isTeacher && (
          <button className="btn btn-primary" onClick={() => setCreating(true)}>
            <Plus size={16} /> Новый курс
          </button>
        )}
      </section>

      {user && mine.length > 0 && (
        <section className="card card-pad">
          <div className="card-head">
            <h2>Мои курсы</h2>
          </div>
          <div className="grid">
            {mine.map((course) => (
              <CourseCard key={course.id} course={course} />
            ))}
          </div>
        </section>
      )}

      <section className="card card-pad">
        <div className="card-head">
          <h2>Все курсы</h2>
        </div>
        {isLoading ? (
          <div className="grid">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} height={180} />
            ))}
          </div>
        ) : courses?.length ? (
          <div className="grid">
            {courses.map((course) => (
              <CourseCard key={course.id} course={enrolled.get(course.id) ?? course} />
            ))}
          </div>
        ) : (
          <Empty icon={<Library size={22} />} title="Курсов пока нет">
            {isTeacher ? 'Создайте первый курс и загрузите в него лекции.' : 'Преподаватели скоро их добавят.'}
          </Empty>
        )}
      </section>

      {creating && <CreateCourseModal onClose={() => setCreating(false)} />}
    </div>
  );
}

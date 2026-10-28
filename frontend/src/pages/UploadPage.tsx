import { CloudUpload, FileVideo, Link2, Plus } from 'lucide-react';
import { type DragEvent, type FormEvent, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router';

import { ApiError } from '../api/client';
import { useCourses, useCreateCourse, useImportLecture, useUploadLecture } from '../api/hooks';
import { useAuth } from '../auth/AuthProvider';
import { Bar, useToast } from '../components/ui';

const ACCEPT = '.mp4,.m4v,.webm,.mov,.mkv,.mp3,.m4a,.wav,.ogg';

function formatSize(bytes: number) {
  return bytes > 1024 ** 3 ? `${(bytes / 1024 ** 3).toFixed(1)} ГБ` : `${Math.round(bytes / 1024 ** 2)} МБ`;
}

export function UploadPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { user } = useAuth();
  const [params] = useSearchParams();

  const { data: courses = [] } = useCourses();
  const createCourse = useCreateCourse();
  const upload = useUploadLecture();
  const importLecture = useImportLecture();

  const [mode, setMode] = useState<'file' | 'url'>('file');
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [courseId, setCourseId] = useState(params.get('course') ?? '');
  const [newCourse, setNewCourse] = useState('');
  const [over, setOver] = useState(false);
  const [progress, setProgress] = useState(0);

  const myCourses = courses.filter((course) => !course.owner_id || course.owner_id === user?.id);
  const busy = upload.isPending || importLecture.isPending || createCourse.isPending;
  const error = upload.error ?? importLecture.error ?? createCourse.error;
  // The same video is already in the library: offer it instead of a second run.
  const duplicate = error instanceof ApiError && error.code === 'lecture_duplicate' ? error.data : null;

  // A new file or link makes an earlier error, such as a duplicate, stale.
  const resetErrors = () => {
    upload.reset();
    importLecture.reset();
  };

  const pickFile = (picked: File | null) => {
    resetErrors();
    setFile(picked);
  };

  const drop = (event: DragEvent) => {
    event.preventDefault();
    setOver(false);
    const dropped = event.dataTransfer.files[0];
    if (dropped) pickFile(dropped);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    send(false);
  };

  const send = async (allowDuplicate: boolean) => {
    let targetCourse = courseId;
    if (courseId === 'new') {
      targetCourse = (await createCourse.mutateAsync({ title: newCourse.trim() })).id;
      // A retry after a duplicate warning must not create the course twice.
      setCourseId(targetCourse);
    }

    const done = (lectureId: string) => {
      toast('Лекция загружена и поставлена в обработку');
      navigate(`/lectures/${lectureId}`);
    };

    if (mode === 'file' && file) {
      const form = new FormData();
      form.append('file', file);
      if (title.trim()) form.append('title', title.trim());
      if (targetCourse) form.append('course_id', targetCourse);
      if (allowDuplicate) form.append('allow_duplicate', 'true');

      upload.mutate({ form, onProgress: setProgress }, { onSuccess: (lecture) => done(lecture.id) });
    } else if (mode === 'url') {
      importLecture.mutate(
        {
          url: url.trim(),
          title: title.trim() || undefined,
          course_id: targetCourse || undefined,
          allow_duplicate: allowDuplicate || undefined,
        },
        { onSuccess: (lecture) => done(lecture.id) },
      );
    }
  };

  const ready =
    (mode === 'file' ? !!file : /^https?:\/\//.test(url.trim())) &&
    (courseId !== 'new' || !!newCourse.trim());

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <div className="eyebrow">Для преподавателей</div>
          <h1>Загрузить лекцию</h1>
          <p>Видео расшифруется, проиндексируется для поиска, и по нему соберётся конспект с оглавлением.</p>
        </div>
      </section>

      <section className="card card-pad" style={{ maxWidth: 760 }}>
        <form className="form" onSubmit={submit}>
          <div className="segmented" style={{ alignSelf: 'flex-start' }}>
            <button type="button" className={mode === 'file' ? 'active' : ''} onClick={() => setMode('file')}>
              <FileVideo size={15} /> Файл
            </button>
            <button type="button" className={mode === 'url' ? 'active' : ''} onClick={() => setMode('url')}>
              <Link2 size={15} /> Ссылка
            </button>
          </div>

          {duplicate ? (
            <div className="alert duplicate-alert">
              <span>
                Эта лекция уже есть в библиотеке: <b>«{String(duplicate.title)}»</b>. Её не нужно обрабатывать
                заново — можно сразу смотреть.
              </span>
              <div className="duplicate-actions">
                <Link className="btn btn-primary btn-sm" to={`/lectures/${String(duplicate.lecture_id)}`}>
                  Открыть лекцию
                </Link>
                <button type="button" className="btn btn-sm" disabled={busy} onClick={() => send(true)}>
                  Всё равно добавить
                </button>
              </div>
            </div>
          ) : (
            error && <div className="alert alert-error">{error.message}</div>
          )}

          {mode === 'file' ? (
            <label
              className={`dropzone${over ? ' over' : ''}`}
              onDragOver={(e) => {
                e.preventDefault();
                setOver(true);
              }}
              onDragLeave={() => setOver(false)}
              onDrop={drop}
            >
              <input type="file" accept={ACCEPT} onChange={(e) => pickFile(e.target.files?.[0] ?? null)} />
              <CloudUpload size={32} strokeWidth={1.5} />
              {file ? (
                <>
                  <b>{file.name}</b>
                  <span className="muted">{formatSize(file.size)} · нажмите, чтобы выбрать другой</span>
                </>
              ) : (
                <>
                  <b>Перетащите видео сюда или нажмите</b>
                  <span className="muted">MP4, WebM, MOV, MKV или аудио</span>
                </>
              )}
            </label>
          ) : (
            <div className="field">
              <label htmlFor="url">Ссылка на видео</label>
              <input
                id="url"
                className="input"
                placeholder="https://www.youtube.com/watch?v=…"
                value={url}
                onChange={(e) => {
                  resetErrors();
                  setUrl(e.target.value);
                }}
              />
              <span className="muted" style={{ fontSize: 13 }}>YouTube, Vimeo, RuTube и сотни других сайтов</span>
            </div>
          )}

          <div className="form-row">
            <div className="field">
              <label htmlFor="title">Название</label>
              <input
                id="title"
                className="input"
                placeholder={mode === 'url' ? 'Возьмём с сайта' : 'Возьмём из имени файла'}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="course">Курс</label>
              <select id="course" className="select" value={courseId} onChange={(e) => setCourseId(e.target.value)}>
                <option value="">Без курса</option>
                {myCourses.map((course) => (
                  <option key={course.id} value={course.id}>
                    {course.title}
                  </option>
                ))}
                <option value="new">+ Новый курс…</option>
              </select>
            </div>
          </div>

          {courseId === 'new' && (
            <div className="field">
              <label htmlFor="new-course">Название нового курса</label>
              <input
                id="new-course"
                className="input"
                value={newCourse}
                onChange={(e) => setNewCourse(e.target.value)}
                autoFocus
              />
            </div>
          )}

          {upload.isPending && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <Bar value={progress} brand />
              <span className="muted" style={{ fontSize: 13 }}>Загрузка: {Math.round(progress * 100)}%</span>
            </div>
          )}

          <button className="btn btn-primary" disabled={!ready || busy} style={{ alignSelf: 'flex-start' }}>
            {mode === 'file' ? <CloudUpload size={16} /> : <Plus size={16} />}
            {!busy ? 'Загрузить и обработать' : mode === 'url' ? 'Проверяем ссылку…' : 'Отправляем…'}
          </button>
        </form>
      </section>
    </div>
  );
}

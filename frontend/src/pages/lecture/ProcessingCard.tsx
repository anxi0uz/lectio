import { RefreshCw } from 'lucide-react';

import type { Lecture } from '../../api/types';
import { Bar, Spinner } from '../../components/ui';
import { PIPELINE, STATUS_LABELS } from '../../lib/format';

/** What went wrong, in words a student understands; details stay below. */
function explainFailure(error: string | null) {
  if (!error) return 'Что-то пошло не так при обработке.';
  if (error.includes('Could not download video')) {
    return 'Не получилось скачать видео: сайт оборвал соединение. Обычно помогает обработать заново.';
  }
  if (error.includes('No speech was recognized')) return 'В записи не нашлось речи, расшифровывать нечего.';
  if (error.includes('neither a video file')) return 'Видеофайл пропал с сервера. Загрузите лекцию заново.';
  return 'Что-то пошло не так при обработке.';
}

export function ProcessingCard({
  lecture,
  canManage,
  onRetry,
  retrying,
}: {
  lecture: Lecture;
  canManage: boolean;
  onRetry: () => void;
  retrying: boolean;
}) {
  if (lecture.status === 'failed') {
    return (
      <section className="processing">
        <h2 style={{ color: 'var(--danger)' }}>Не удалось обработать лекцию</h2>
        <p style={{ marginTop: 8, fontSize: 17 }}>{explainFailure(lecture.error)}</p>
        <div className="actions" style={{ marginTop: 16, alignItems: 'center' }}>
          {canManage && (
            <button className="btn btn-primary btn-sm" onClick={onRetry} disabled={retrying}>
              <RefreshCw size={14} /> Обработать заново
            </button>
          )}
          {lecture.error && (
            <details>
              <summary className="label muted" style={{ cursor: 'pointer' }}>
                Технические подробности
              </summary>
              <pre className="mono" style={{ margin: '10px 0 0', fontSize: 12, whiteSpace: 'pre-wrap', color: 'var(--ink-2)' }}>
                {lecture.error}
              </pre>
            </details>
          )}
        </div>
      </section>
    );
  }

  // Uploaded files skip the download stage.
  const stages = lecture.source_type === 'url' ? PIPELINE : PIPELINE.slice(1);
  const current = lecture.status === 'pending' ? -1 : stages.indexOf(lecture.status);

  return (
    <section className="processing">
      <h2 style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Spinner size={20} />
        {lecture.status === 'pending'
          ? 'Лекция в очереди'
          : `${STATUS_LABELS[lecture.status]} — ${Math.round(lecture.progress * 100)}%`}
      </h2>
      <p className="muted" style={{ marginTop: 8 }}>
        Страница обновится сама. Расшифровка и поиск появятся после индексации, конспект — чуть позже.
      </p>
      <div className="steps">
        {stages.map((stage, index) => (
          <div key={stage} className={`step${index < current ? ' done' : index === current ? ' current' : ''}`}>
            <Bar value={index === current ? lecture.progress : 0} />
            {String(index + 1).padStart(2, '0')} {STATUS_LABELS[stage]}
          </div>
        ))}
      </div>
    </section>
  );
}

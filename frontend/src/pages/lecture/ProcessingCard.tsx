import { AlertTriangle, RefreshCw } from 'lucide-react';

import type { Lecture } from '../../api/types';
import { Bar, Spinner } from '../../components/ui';
import { PIPELINE, STATUS_LABELS } from '../../lib/format';

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
      <div className="alert alert-error" style={{ flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', fontWeight: 600 }}>
          <AlertTriangle size={18} /> Не удалось обработать лекцию
        </div>
        {lecture.error && <code style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>{lecture.error}</code>}
        {canManage && (
          <button className="btn btn-sm" onClick={onRetry} disabled={retrying} style={{ alignSelf: 'flex-start' }}>
            <RefreshCw size={14} /> Обработать заново
          </button>
        )}
      </div>
    );
  }

  // Uploaded files skip the download stage.
  const stages = lecture.source_type === 'url' ? PIPELINE : PIPELINE.slice(1);
  const current = lecture.status === 'pending' ? -1 : stages.indexOf(lecture.status);

  return (
    <div className="card card-pad">
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Spinner />
        <h3>
          {lecture.status === 'pending'
            ? 'Лекция в очереди на обработку'
            : `${STATUS_LABELS[lecture.status]}: ${Math.round(lecture.progress * 100)}%`}
        </h3>
      </div>
      <p className="muted" style={{ marginTop: 6, fontSize: 14 }}>
        Страница обновится сама. Расшифровка и поиск станут доступны после индексации, конспект — чуть позже.
      </p>
      <div className="steps">
        {stages.map((stage, index) => (
          <div
            key={stage}
            className={`step${index < current ? ' done' : index === current ? ' current' : ''}`}
          >
            <Bar value={index === current ? lecture.progress : 0} />
            {STATUS_LABELS[stage]}
          </div>
        ))}
      </div>
    </div>
  );
}

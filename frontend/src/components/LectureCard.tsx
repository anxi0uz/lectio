import { Clock, FileVideo, Play } from 'lucide-react';
import { Link } from 'react-router';

import { isProcessing } from '../api/hooks';
import type { Lecture } from '../api/types';
import { duration, STATUS_LABELS, timecode } from '../lib/format';
import { Bar, StatusBadge } from './ui';

export function Thumbnail({
  lecture,
  watched,
}: {
  lecture: Lecture;
  watched?: number;
}) {
  return (
    <div className="thumb">
      {lecture.video_url ? (
        // A frame a few seconds in stands in for a poster image.
        <video src={`${lecture.video_url}#t=8`} preload="metadata" muted playsInline />
      ) : (
        <FileVideo size={36} strokeWidth={1.4} />
      )}

      {isProcessing(lecture) && (
        <div className="thumb-status">
          <span>{STATUS_LABELS[lecture.status]}…</span>
          <Bar value={lecture.progress} />
        </div>
      )}

      {lecture.duration_seconds != null && (
        <span className="thumb-duration">{timecode(lecture.duration_seconds)}</span>
      )}

      {watched != null && lecture.duration_seconds ? (
        <div className="thumb-progress">
          <div style={{ width: `${Math.min(watched / lecture.duration_seconds, 1) * 100}%` }} />
        </div>
      ) : null}
    </div>
  );
}

export function LectureCard({
  lecture,
  watched,
  courseTitle,
}: {
  lecture: Lecture;
  watched?: number;
  courseTitle?: string;
}) {
  return (
    <Link to={`/lectures/${lecture.id}${watched ? `?t=${Math.floor(watched)}` : ''}`} className="lecture-card">
      <Thumbnail lecture={lecture} watched={watched} />
      <div className="lecture-card-body">
        {courseTitle && <span className="eyebrow" style={{ margin: 0 }}>{courseTitle}</span>}
        <div className="lecture-card-title">{lecture.title}</div>
        <div className="lecture-card-meta">
          {lecture.status === 'ready' ? (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
              <Clock size={14} />
              {duration(lecture.duration_seconds)}
            </span>
          ) : (
            <StatusBadge status={lecture.status} />
          )}
          {watched != null && (
            <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <Play size={13} />
              {timecode(watched)}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}

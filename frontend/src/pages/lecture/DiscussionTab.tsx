import { MessagesSquare, Trash2 } from 'lucide-react';
import { type FormEvent, useState } from 'react';

import { useCommentActions, useComments } from '../../api/hooks';
import type { PublicUser } from '../../api/types';
import { Avatar, Empty, Spinner, useToast } from '../../components/ui';
import { fullName, relativeDate, timecode } from '../../lib/format';

export function DiscussionTab({
  lectureId,
  user,
  canManage,
  time,
  onSeek,
}: {
  lectureId: string;
  user: PublicUser | null;
  canManage: boolean;
  time: number;
  onSeek: (seconds: number) => void;
}) {
  const toast = useToast();
  const comments = useComments(lectureId);
  const actions = useCommentActions(lectureId);
  const [text, setText] = useState('');
  const [atMoment, setAtMoment] = useState(true);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    actions.create.mutate(
      { text: text.trim(), position_seconds: atMoment && time > 1 ? Math.floor(time) : undefined },
      {
        onSuccess: () => setText(''),
        onError: (error) => toast(error.message, { error: true }),
      },
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {user ? (
        <form className="comment-form" onSubmit={submit}>
          <textarea
            className="textarea"
            rows={3}
            maxLength={2000}
            placeholder="Вопрос, уточнение или мысль по лекции"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="comment-form-row">
            <label className="comment-moment">
              <input type="checkbox" checked={atMoment} onChange={(e) => setAtMoment(e.target.checked)} />
              {time > 1 ? `О моменте ${timecode(time)}` : 'О текущем моменте видео'}
            </label>
            <button className="btn btn-primary btn-sm" disabled={!text.trim() || actions.create.isPending}>
              Отправить
            </button>
          </div>
        </form>
      ) : (
        <p className="muted" style={{ fontSize: 14 }}>
          Войдите, чтобы задать вопрос или оставить комментарий.
        </p>
      )}

      {comments.isPending ? (
        <Spinner />
      ) : comments.data?.length ? (
        <div>
          {comments.data.map((comment) => (
            <div key={comment.id} className="comment">
              <Avatar user={comment.author} size={36} />
              <div className="comment-body">
                <div className="comment-meta">
                  <b>{fullName(comment.author)}</b>
                  {comment.author.role === 'teacher' && <span className="comment-role">преподаватель</span>}
                  <span className="muted">{relativeDate(comment.created_at)}</span>
                  {comment.position_seconds != null && (
                    <button className="time-chip" onClick={() => onSeek(comment.position_seconds!)}>
                      ▶ {timecode(comment.position_seconds)}
                    </button>
                  )}
                </div>
                <div className="comment-text">{comment.text}</div>
              </div>
              {(comment.author.id === user?.id || canManage) && (
                <button
                  className="btn btn-ghost btn-sm btn-icon btn-danger"
                  aria-label="Удалить комментарий"
                  onClick={() => actions.remove.mutate(comment.id)}
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
          ))}
        </div>
      ) : (
        <Empty icon={<MessagesSquare size={22} />} title="Пока тихо">
          Здесь студенты и преподаватель обсуждают лекцию. Комментарий можно привязать к моменту видео.
        </Empty>
      )}
    </div>
  );
}

import { BookMarked, Trash2 } from 'lucide-react';
import { Link } from 'react-router';

import { useAllBookmarks, useBookmarkActions } from '../api/hooks';
import type { BookmarkWithLecture } from '../api/types';
import { Empty, Skeleton } from '../components/ui';
import { relativeDate, timecode } from '../lib/format';

export function BookmarksPage() {
  const { data: bookmarks, isLoading } = useAllBookmarks();
  const actions = useBookmarkActions();

  const grouped = new Map<string, BookmarkWithLecture[]>();
  for (const bookmark of bookmarks ?? []) {
    grouped.set(bookmark.lecture_id, [...(grouped.get(bookmark.lecture_id) ?? []), bookmark]);
  }

  return (
    <div className="page">
      <section className="card page-header">
        <div>
          <div className="eyebrow">Моё</div>
          <h1>Заметки</h1>
          <p>Отмеченные моменты лекций. Нажмите на таймкод, чтобы вернуться к нему.</p>
        </div>
      </section>

      {isLoading ? (
        <Skeleton height={200} />
      ) : grouped.size ? (
        [...grouped.entries()].map(([lectureId, items]) => (
          <section key={lectureId} className="card card-pad">
            <div className="card-head">
              <Link to={`/lectures/${lectureId}`}>
                <h2>{items[0].lecture_title}</h2>
              </Link>
              <span className="muted" style={{ fontSize: 13 }}>
                {items.length} шт.
              </span>
            </div>
            {[...items]
              .sort((a, b) => a.position_seconds - b.position_seconds)
              .map((bookmark) => (
                <div key={bookmark.id} className="bookmark">
                  <Link
                    to={`/lectures/${lectureId}?t=${Math.floor(bookmark.position_seconds)}`}
                    className="time-chip"
                  >
                    ▶ {timecode(bookmark.position_seconds)}
                  </Link>
                  <span className="bookmark-note">{bookmark.note || <span className="muted">Без заметки</span>}</span>
                  <span className="muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                    {relativeDate(bookmark.created_at)}
                  </span>
                  <button
                    className="btn btn-ghost btn-sm btn-icon btn-danger"
                    aria-label="Удалить"
                    onClick={() => actions.remove.mutate(bookmark.id)}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
          </section>
        ))
      ) : (
        <section className="card">
          <Empty icon={<BookMarked size={22} />} title="Заметок пока нет">
            Во время просмотра нажмите <b>B</b> или значок закладки на видео.
          </Empty>
        </section>
      )}
    </div>
  );
}

import { BookMarked, Hash, ListTree, Pencil, Search, Sparkles, Trash2 } from 'lucide-react';
import { type FormEvent, useState } from 'react';

import { useBookmarkActions, useSearch } from '../../api/hooks';
import type { Bookmark, Chapter, KeyTerm, Segment, Summary } from '../../api/types';
import { Markdown } from '../../components/Markdown';
import { Empty, Spinner, useToast } from '../../components/ui';
import { timecode } from '../../lib/format';
import { TranscriptPanel } from './TranscriptPanel';

export function SummaryTab({
  summary,
  processing,
  canManage,
  onRegenerate,
  regenerating,
}: {
  summary?: Summary;
  processing: boolean;
  canManage: boolean;
  onRegenerate: () => void;
  regenerating: boolean;
}) {
  if (summary?.summary) {
    return <Markdown>{summary.summary}</Markdown>;
  }

  if (processing || summary?.status === 'summarizing') {
    return (
      <Empty icon={<Spinner />} title="Конспект готовится">
        Языковая модель читает расшифровку и составляет конспект. Обычно это пара минут.
      </Empty>
    );
  }

  return (
    <Empty
      icon={<Sparkles size={22} />}
      title="Конспекта пока нет"
      action={
        canManage && (
          <button className="btn btn-sm" onClick={onRegenerate} disabled={regenerating}>
            <Sparkles size={14} /> Сгенерировать
          </button>
        )
      }
    >
      {summary?.error
        ? 'Языковая модель была недоступна во время обработки. Расшифровка и поиск при этом работают.'
        : 'Конспект появится после обработки лекции.'}
    </Empty>
  );
}

export function ChaptersTab({
  chapters,
  time,
  onSeek,
}: {
  chapters: Chapter[];
  time: number;
  onSeek: (seconds: number) => void;
}) {
  if (!chapters.length) {
    return <Empty icon={<ListTree size={22} />} title="Оглавления пока нет">Оно строится вместе с конспектом.</Empty>;
  }

  const starts = chapters.flatMap((c) => [c.start_seconds, ...c.subsections.map((s) => s.start_seconds)]);
  const currentStart = starts.filter((s) => s <= time).at(-1);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {chapters.map((chapter) => (
        <div key={chapter.id}>
          <button
            className={`chapter${chapter.start_seconds === currentStart ? ' active' : ''}`}
            onClick={() => onSeek(chapter.start_seconds)}
          >
            <span className="time-chip">{timecode(chapter.start_seconds)}</span>
            <span className="chapter-title">{chapter.title}</span>
          </button>
          {chapter.subsections.map((sub) => (
            <button
              key={sub.id}
              className={`chapter sub${sub.start_seconds === currentStart && sub.start_seconds !== chapter.start_seconds ? ' active' : ''}`}
              onClick={() => onSeek(sub.start_seconds)}
            >
              <span className="time-chip">{timecode(sub.start_seconds)}</span>
              <span className="chapter-title">{sub.title}</span>
            </button>
          ))}
        </div>
      ))}
    </div>
  );
}

export function TermsTab({ terms, onSeek }: { terms: KeyTerm[]; onSeek: (seconds: number) => void }) {
  if (!terms.length) {
    return <Empty icon={<Hash size={22} />} title="Терминов пока нет">Ключевые понятия выделяются вместе с конспектом.</Empty>;
  }

  return (
    <div className="terms">
      {terms.map((term) => (
        <div key={term.term} className="term">
          <div className="term-name">{term.term}</div>
          <div className="term-def">{term.definition}</div>
          {term.start_seconds != null && (
            <button
              className="time-chip"
              style={{ alignSelf: 'flex-start' }}
              onClick={() => onSeek(term.start_seconds!)}
            >
              ▶ впервые на {timecode(term.start_seconds)}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}

export function TranscriptTab({
  lectureId,
  segments,
  time,
  onSeek,
}: {
  lectureId: string;
  segments: Segment[];
  time: number;
  onSeek: (seconds: number) => void;
}) {
  const [draft, setDraft] = useState('');
  const [query, setQuery] = useState('');
  const results = useSearch(query, { lectureId }, 5);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setQuery(draft.trim());
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <form onSubmit={submit} style={{ display: 'flex', gap: 8 }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <Search size={16} className="muted" style={{ position: 'absolute', left: 12, top: 13 }} />
          <input
            className="input"
            style={{ paddingLeft: 36 }}
            placeholder="Поиск по смыслу внутри лекции"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
        </div>
        <button className="btn" disabled={!draft.trim()}>
          {results.isFetching ? <Spinner size={14} /> : 'Найти'}
        </button>
      </form>

      {query && (
        <div className="card" style={{ padding: 6 }}>
          {results.data?.length ? (
            results.data.map((hit) => (
              <button
                key={hit.chunk_id}
                className="search-result"
                style={{ border: 0, background: 'transparent', textAlign: 'left', width: '100%' }}
                onClick={() => onSeek(hit.start_seconds)}
              >
                <span className="search-result-head">
                  <span className="time-chip">{timecode(hit.start_seconds)}</span>
                </span>
                <span className="search-result-text" dangerouslySetInnerHTML={{ __html: hit.highlight }} />
              </button>
            ))
          ) : (
            !results.isFetching && <p className="muted" style={{ padding: 14 }}>Ничего не нашлось</p>
          )}
        </div>
      )}

      <div className="card" style={{ paddingTop: 12 }}>
        <TranscriptPanel segments={segments} time={time} onSeek={onSeek} maxHeight={560} withFilter />
      </div>
    </div>
  );
}

export function BookmarksTab({
  lectureId,
  bookmarks,
  time,
  signedIn,
  onSeek,
}: {
  lectureId: string;
  bookmarks: Bookmark[];
  time: number;
  signedIn: boolean;
  onSeek: (seconds: number) => void;
}) {
  const toast = useToast();
  const actions = useBookmarkActions(lectureId);
  const [note, setNote] = useState('');
  const [editing, setEditing] = useState<{ id: string; note: string } | null>(null);

  if (!signedIn) {
    return (
      <Empty icon={<BookMarked size={22} />} title="Заметки на таймкодах">
        Войдите, чтобы отмечать важные моменты и возвращаться к ним.
      </Empty>
    );
  }

  const add = (event: FormEvent) => {
    event.preventDefault();
    actions.create.mutate(
      { position_seconds: Math.floor(time), note: note.trim() || undefined },
      {
        onSuccess: () => {
          setNote('');
          toast(`Заметка на ${timecode(time)} сохранена`);
        },
        onError: (error) => toast(error.message, { error: true }),
      },
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <form onSubmit={add} style={{ display: 'flex', gap: 8 }}>
        <span className="time-chip" style={{ alignSelf: 'center', cursor: 'default' }}>
          {timecode(time)}
        </span>
        <input
          className="input"
          placeholder="Что важно в этом моменте? (необязательно)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <button className="btn btn-primary" disabled={actions.create.isPending}>
          Сохранить
        </button>
      </form>

      {bookmarks.length ? (
        <div>
          {bookmarks.map((bookmark) => (
            <div key={bookmark.id} className="bookmark">
              <button className="time-chip" onClick={() => onSeek(bookmark.position_seconds)}>
                {timecode(bookmark.position_seconds)}
              </button>
              {editing?.id === bookmark.id ? (
                <form
                  style={{ flex: 1, display: 'flex', gap: 6 }}
                  onSubmit={(e) => {
                    e.preventDefault();
                    actions.update.mutate(editing, { onSuccess: () => setEditing(null) });
                  }}
                >
                  <input
                    className="input"
                    autoFocus
                    value={editing.note}
                    onChange={(e) => setEditing({ ...editing, note: e.target.value })}
                  />
                  <button className="btn btn-sm">OK</button>
                </form>
              ) : (
                <span className="bookmark-note">{bookmark.note || <span className="muted">Без заметки</span>}</span>
              )}
              <button
                className="btn btn-ghost btn-sm btn-icon"
                aria-label="Изменить"
                onClick={() => setEditing({ id: bookmark.id, note: bookmark.note ?? '' })}
              >
                <Pencil size={14} />
              </button>
              <button
                className="btn btn-ghost btn-sm btn-icon btn-danger"
                aria-label="Удалить"
                onClick={() => actions.remove.mutate(bookmark.id)}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted" style={{ fontSize: 14 }}>
          Здесь будут ваши отметки. Нажмите <b>B</b> во время просмотра, чтобы быстро поставить закладку.
        </p>
      )}
    </div>
  );
}

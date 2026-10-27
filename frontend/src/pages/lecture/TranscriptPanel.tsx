import { ListVideo, Search } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';

import type { Segment } from '../../api/types';
import { timecode } from '../../lib/format';
import { segmentAt } from './Player';

/** Follows playback: the current line is highlighted and kept in view. */
export function TranscriptPanel({
  segments,
  time,
  onSeek,
  maxHeight = 420,
  withFilter = false,
}: {
  segments: Segment[];
  time: number;
  onSeek: (seconds: number) => void;
  maxHeight?: number;
  withFilter?: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);
  const userScrolledAt = useRef(0);
  const [filter, setFilter] = useState('');

  const active = segmentAt(segments, time);
  const visible = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return needle
      ? segments.filter((segment) => segment.text.toLowerCase().includes(needle))
      : segments;
  }, [segments, filter]);

  useEffect(() => {
    // Leave the list alone for a while after the user scrolled it.
    if (filter || Date.now() - userScrolledAt.current < 4000) return;

    const container = box.current;
    const line = container?.querySelector<HTMLElement>('.transcript-line.active');
    if (!container || !line) return;

    container.scrollTo({
      top: line.offsetTop - container.clientHeight / 3,
      behavior: 'smooth',
    });
  }, [active, filter]);

  if (!segments.length) {
    return (
      <p className="muted" style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '8px 0' }}>
        <ListVideo size={18} /> Расшифровка появится после обработки
      </p>
    );
  }

  return (
    <>
      {withFilter && (
        <div style={{ position: 'relative', marginBottom: 12 }}>
          <Search size={15} className="muted" style={{ position: 'absolute', left: 14, top: 15 }} />
          <input
            className="input"
            style={{ paddingLeft: 38 }}
            placeholder="Найти слово в расшифровке"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </div>
      )}
      <div
        ref={box}
        className="transcript"
        style={{ maxHeight }}
        onWheel={() => (userScrolledAt.current = Date.now())}
        onTouchMove={() => (userScrolledAt.current = Date.now())}
      >
        {visible.map((segment) => {
          const index = segment.position;
          const state = index === active ? ' active' : index < active ? ' past' : '';

          return (
            <button
              key={segment.id}
              className={`transcript-line${state}`}
              onClick={() => onSeek(segment.start_seconds)}
            >
              <span className="ts">{timecode(segment.start_seconds)}</span>
              <span>{segment.text}</span>
            </button>
          );
        })}
        {!visible.length && <p className="muted" style={{ padding: '12px 0' }}>Ничего не нашлось</p>}
      </div>
    </>
  );
}

/** The phrase being spoken right now, large, above the running transcript. */
export function NowSpeaking({
  segments,
  time,
  onSeek,
}: {
  segments: Segment[];
  time: number;
  onSeek: (seconds: number) => void;
}) {
  const index = segmentAt(segments, time);
  const current = segments[Math.max(index, 0)];

  return (
    <section className="now" aria-label="Расшифровка">
      <h2 className="now-head label">
        <span className="dot" />
        Сейчас говорит{current ? ` · ${timecode(current.start_seconds)}` : ''}
      </h2>
      {current ? (
        <>
          <p className="now-quote">«{current.text}»</p>
          <TranscriptPanel segments={segments} time={time} onSeek={onSeek} maxHeight={300} />
        </>
      ) : (
        <p className="muted">Расшифровка появится после обработки</p>
      )}
    </section>
  );
}

import { Search, Sparkles } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router';

import { useCourses, useSearch, useSearchHistory } from '../api/hooks';
import { Empty, Skeleton } from '../components/ui';
import { timecode } from '../lib/format';

const EXAMPLES = [
  'как доказать теорему через площади',
  'чем катет отличается от гипотенузы',
  'Pythagorean theorem proof',
];

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const query = params.get('q') ?? '';
  const courseId = params.get('course') ?? '';
  const [draft, setDraft] = useState(query);

  const { data: courses = [] } = useCourses();
  const { data: history = [] } = useSearchHistory();
  const results = useSearch(query, { courseId: courseId || undefined }, 20);

  useEffect(() => setDraft(query), [query]);

  const run = (q: string, course = courseId) => {
    const next = new URLSearchParams();
    if (q.trim()) next.set('q', q.trim());
    if (course) next.set('course', course);
    setParams(next);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    run(draft);
  };

  return (
    <div className="page">
      <section className="card page-header" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
        <div>
          <div className="eyebrow">Умный поиск</div>
          <h1>Поиск по смыслу во всех лекциях</h1>
          <p>Формулируйте как угодно — найдём фрагмент, даже если в лекции говорили другими словами или на другом языке.</p>
        </div>
        <form onSubmit={submit} style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <div style={{ position: 'relative', flex: '1 1 320px' }}>
            <Search size={17} className="muted" style={{ position: 'absolute', left: 14, top: 13 }} />
            <input
              className="input"
              style={{ paddingLeft: 40, height: 44 }}
              placeholder="Например: «зачем строить квадрат со стороной a + b»"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoFocus
            />
          </div>
          <select
            className="select"
            style={{ flex: '0 1 220px', height: 44 }}
            value={courseId}
            onChange={(e) => run(draft, e.target.value)}
          >
            <option value="">Во всех курсах</option>
            {courses.map((course) => (
              <option key={course.id} value={course.id}>
                {course.title}
              </option>
            ))}
          </select>
          <button className="btn btn-primary" style={{ height: 44 }}>
            Найти
          </button>
        </form>
      </section>

      <section className="card" style={{ padding: 8 }}>
        {!query ? (
          <div className="card-pad">
            <h3 style={{ marginBottom: 12 }}>Попробуйте</h3>
            <div className="chips">
              {(history.length ? history.map((h) => h.query) : EXAMPLES).map((text) => (
                <button key={text} className="chip" onClick={() => run(text)}>
                  <Sparkles size={13} /> {text}
                </button>
              ))}
            </div>
          </div>
        ) : results.isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: 16 }}>
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} height={84} />
            ))}
          </div>
        ) : results.error ? (
          <div className="alert alert-error" style={{ margin: 16 }}>{results.error.message}</div>
        ) : results.data?.length ? (
          <div style={{ opacity: results.isFetching ? 0.6 : 1, transition: 'opacity 0.2s' }}>
            {results.data.map((hit) => (
              <Link
                key={hit.chunk_id}
                to={`/lectures/${hit.lecture_id}?t=${Math.floor(hit.start_seconds)}`}
                className="search-result"
              >
                <span className="search-result-head">
                  <span className="time-chip">▶ {timecode(hit.start_seconds)}</span>
                  <span style={{ fontWeight: 600, color: 'var(--text)' }}>{hit.lecture_title}</span>
                </span>
                <span className="search-result-text" dangerouslySetInnerHTML={{ __html: hit.highlight }} />
              </Link>
            ))}
          </div>
        ) : (
          <Empty icon={<Search size={22} />} title="Ничего не нашлось">
            Попробуйте переформулировать запрос или искать во всех курсах.
          </Empty>
        )}
      </section>
    </div>
  );
}

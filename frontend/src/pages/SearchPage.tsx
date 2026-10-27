import { Search } from 'lucide-react';
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
      <section className="page-header" style={{ gridTemplateColumns: '1fr' }}>
        <div>
          <div className="eyebrow">Умный поиск</div>
          <h1>
            Поиск <span className="accent">по смыслу</span> во всех лекциях
          </h1>
          <p>Формулируйте как угодно — найдём фрагмент, даже если в лекции говорили другими словами или на другом языке.</p>
        </div>
        <form onSubmit={submit} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
          <div style={{ position: 'relative', flex: '1 1 320px' }}>
            <Search size={17} className="muted" style={{ position: 'absolute', left: 14, top: 17 }} />
            <input
              className="input"
              style={{ paddingLeft: 42, height: 52, fontSize: 17 }}
              placeholder="Например: «зачем строить квадрат со стороной a + b»"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoFocus
            />
          </div>
          <select
            className="select"
            style={{ flex: '0 1 240px', height: 52 }}
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
          <button className="btn btn-accent" style={{ height: 52 }}>
            Найти
          </button>
        </form>
      </section>

      <section>
        {!query ? (
          <div className="card card-pad">
            <h3 className="label" style={{ marginBottom: 16 }}>{history.length ? 'Вы искали' : 'Попробуйте'}</h3>
            <div className="chips">
              {(history.length ? history.map((h) => h.query) : EXAMPLES).map((text) => (
                <button key={text} className="chip" onClick={() => run(text)}>
                  {text}
                </button>
              ))}
            </div>
          </div>
        ) : results.isLoading ? (
          <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingTop: 24 }}>
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} height={84} />
            ))}
          </div>
        ) : results.error ? (
          <div className="alert alert-error">{results.error.message}</div>
        ) : results.data?.length ? (
          <div style={{ opacity: results.isFetching ? 0.6 : 1, transition: 'opacity 0.2s' }}>
            {results.data.map((hit) => (
              <Link
                key={hit.chunk_id}
                to={`/lectures/${hit.lecture_id}?t=${Math.floor(hit.start_seconds)}`}
                className="search-result"
              >
                <span className="search-result-time">{timecode(hit.start_seconds)}</span>
                <span>
                  <span className="search-result-title">{hit.lecture_title}</span>
                  <span className="search-result-text" style={{ display: 'block' }} dangerouslySetInnerHTML={{ __html: hit.highlight }} />
                </span>
              </Link>
            ))}
          </div>
        ) : (
          <Empty icon={<Search size={24} />} title="Ничего не нашлось">
            Попробуйте переформулировать запрос или искать во всех курсах.
          </Empty>
        )}
      </section>
    </div>
  );
}

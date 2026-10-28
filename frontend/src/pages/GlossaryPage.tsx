import { BookA, Search } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router';

import { useCourses, useGlossary } from '../api/hooks';
import type { GlossaryEntry } from '../api/types';
import { Empty, Skeleton } from '../components/ui';
import { plural, timecode } from '../lib/format';

function letterOf(entry: GlossaryEntry) {
  return entry.term.charAt(0).toLocaleUpperCase('ru');
}

export function GlossaryPage() {
  const { data: courses = [] } = useCourses();
  const [input, setInput] = useState('');
  const [query, setQuery] = useState('');
  const [courseId, setCourseId] = useState('');

  // Ask the server once typing pauses, not on every key.
  useEffect(() => {
    const timer = setTimeout(() => setQuery(input.trim()), 250);
    return () => clearTimeout(timer);
  }, [input]);

  const { data: entries, isLoading } = useGlossary(query, courseId);

  const letters = new Map<string, GlossaryEntry[]>();
  for (const entry of entries ?? []) {
    const letter = letterOf(entry);
    letters.set(letter, [...(letters.get(letter) ?? []), entry]);
  }

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <div className="eyebrow">По всем лекциям</div>
          <h1>Глоссарий</h1>
          <p>
            Ключевые понятия из конспектов всех лекций. Новые лекции попадают сюда сами, как только готов конспект.
          </p>
        </div>
      </section>

      <section className="glossary-filters">
        <label className="glossary-search">
          <Search size={16} />
          <input
            className="input"
            placeholder="Найти термин или слово в определении"
            value={input}
            onChange={(e) => setInput(e.target.value)}
          />
        </label>
        <select className="select" value={courseId} onChange={(e) => setCourseId(e.target.value)}>
          <option value="">Все курсы</option>
          {courses.map((course) => (
            <option key={course.id} value={course.id}>
              {course.title}
            </option>
          ))}
        </select>
      </section>

      {letters.size > 1 && (
        <nav className="glossary-letters" aria-label="Буквы">
          {[...letters.keys()].map((letter) => (
            <a key={letter} href={`#letter-${letter}`}>
              {letter}
            </a>
          ))}
        </nav>
      )}

      {isLoading ? (
        <Skeleton height={300} />
      ) : letters.size ? (
        <>
          <p className="muted" style={{ fontSize: 14 }}>
            {plural(entries!.length, 'термин', 'термина', 'терминов')}
          </p>
          {[...letters.entries()].map(([letter, items]) => (
            <section key={letter} id={`letter-${letter}`} className="glossary-letter">
              <h2>{letter}</h2>
              <div className="terms">
                {items.map((entry) => (
                  <div key={entry.term} className="term">
                    <div className="term-name">{entry.term}</div>
                    {entry.mentions.map((mention) => (
                      <div key={mention.lecture_id} className="glossary-mention">
                        <div className="term-def">{mention.definition}</div>
                        <Link
                          className="glossary-source"
                          to={`/lectures/${mention.lecture_id}${
                            mention.start_seconds != null ? `?t=${Math.floor(mention.start_seconds)}` : ''
                          }`}
                        >
                          <span className="time-chip">
                            ▶ {mention.start_seconds != null ? timecode(mention.start_seconds) : 'открыть'}
                          </span>
                          <span>{mention.lecture_title}</span>
                        </Link>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </section>
          ))}
        </>
      ) : (
        <section className="card">
          <Empty icon={<BookA size={22} />} title={query ? 'Ничего не нашлось' : 'Терминов пока нет'}>
            {query
              ? 'Попробуйте другое слово или уберите фильтр по курсу.'
              : 'Термины появляются вместе с конспектом лекции.'}
          </Empty>
        </section>
      )}
    </div>
  );
}

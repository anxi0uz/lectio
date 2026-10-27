import { type FormEvent, useEffect, useRef, useState } from 'react';

import { messageForCode, streamEvents } from '../../api/client';
import type { Chapter, ChatMessage, SearchHit } from '../../api/types';
import { Markdown } from '../../components/Markdown';
import { timecode } from '../../lib/format';

type Turn = ChatMessage & { sources?: SearchHit[]; error?: boolean; streaming?: boolean };

const SUGGESTIONS = [
  'О чём эта лекция в двух словах?',
  'Какие определения здесь даются?',
  'Объясни самое сложное место попроще',
];

const QUOTE_CHARS = 110;

function quote(text: string) {
  return text.length > QUOTE_CHARS ? `${text.slice(0, QUOTE_CHARS).trimEnd()}…` : text;
}

/** The section of the lecture a moment belongs to, for source labels. */
function chapterAt(chapters: Chapter[], seconds: number) {
  return chapters.filter((chapter) => chapter.start_seconds <= seconds).at(-1)?.title;
}

export function ChatPanel({
  lectureId,
  enabled,
  chapters,
  onOpenSource,
}: {
  lectureId: string;
  enabled: boolean;
  chapters: Chapter[];
  onOpenSource: (hit: SearchHit) => void;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState('');
  const [pending, setPending] = useState(false);
  const log = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);

  // A new lecture starts a new conversation; an unfinished answer is dropped.
  useEffect(() => {
    setTurns([]);
    return () => abort.current?.abort();
  }, [lectureId]);

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: 'smooth' });
  }, [turns]);

  const updateAnswer = (patch: (turn: Turn) => Turn) =>
    setTurns((current) => [...current.slice(0, -1), patch(current[current.length - 1])]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || pending) return;

    const history = turns
      .filter((turn) => !turn.error)
      .map(({ role, content }) => ({ role, content }));

    setTurns((current) => [
      ...current,
      { role: 'user', content: trimmed },
      { role: 'assistant', content: '', streaming: true },
    ]);
    setQuestion('');
    setPending(true);

    const controller = new AbortController();
    abort.current = controller;

    const fail = (message: string) =>
      updateAnswer((turn) => ({ ...turn, content: message, error: true, streaming: false }));

    try {
      await streamEvents(
        '/qa/stream',
        { question: trimmed, lecture_id: lectureId, history },
        {
          sources: (data) => updateAnswer((turn) => ({ ...turn, sources: data as SearchHit[] })),
          delta: (data) =>
            updateAnswer((turn) => ({ ...turn, content: turn.content + (data as { text: string }).text })),
          error: (data) => {
            const { code } = data as { code?: string };
            fail(messageForCode(code) ?? 'Не удалось получить ответ');
          },
        },
        controller.signal,
      );
      updateAnswer((turn) => ({ ...turn, streaming: false }));
    } catch (error) {
      if ((error as Error).name !== 'AbortError') fail((error as Error).message);
    } finally {
      setPending(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void send(question);
  };

  /** Sources the answer actually cites; all of them if it cites none. */
  const cited = (turn: Turn) => {
    const sources = turn.sources ?? [];
    const numbers = new Set([...turn.content.matchAll(/\[(\d{1,2})\]/g)].map((m) => Number(m[1])));
    const used = sources.map((hit, i) => ({ hit, n: i + 1 })).filter(({ n }) => numbers.has(n));
    return used.length ? used : sources.map((hit, i) => ({ hit, n: i + 1 }));
  };

  return (
    <section className="panel" aria-label="Вопрос к лекции">
      <div className="panel-head">
        <h3>Спросите лекцию</h3>
        <span className="label muted" style={{ fontSize: 11 }}>
          {pending ? 'ищет в расшифровке…' : 'ответ по расшифровке'}
        </span>
      </div>

      {enabled ? (
        <>
          <div ref={log} className="chat">
            {turns.map((turn, index) =>
              turn.role === 'user' ? (
                <p key={index} className="bubble-user">
                  {turn.content}
                </p>
              ) : (
                <div key={index} className={`answer${turn.error ? ' answer-error' : ''}`}>
                  {turn.content ? (
                    <Markdown
                      onCite={(n) => {
                        const hit = turn.sources?.[n - 1];
                        if (hit) onOpenSource(hit);
                      }}
                    >
                      {turn.content}
                    </Markdown>
                  ) : (
                    <span className="typing" aria-label="Печатает">
                      <span />
                      <span />
                      <span />
                    </span>
                  )}

                  {!turn.streaming && !turn.error && !!turn.sources?.length && (
                    <div className="sources">
                      <span className="label">Источники в лекции</span>
                      {cited(turn).map(({ hit, n }) => (
                        <button key={hit.chunk_id} className="source" onClick={() => onOpenSource(hit)}>
                          <span className="source-n">{n}</span>
                          <span className="source-time">▶ {timecode(hit.start_seconds)}</span>
                          <span>
                            <span className="source-title">
                              {hit.lecture_id === lectureId
                                ? chapterAt(chapters, hit.start_seconds) ?? 'Фрагмент лекции'
                                : hit.lecture_title}
                            </span>
                            <span className="source-quote">«{quote(hit.text)}»</span>
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ),
            )}

            {!turns.length && (
              <div className="suggestions">
                {SUGGESTIONS.map((text) => (
                  <button key={text} onClick={() => void send(text)}>
                    {text}
                  </button>
                ))}
              </div>
            )}
          </div>

          <form className="chat-form" onSubmit={submit}>
            <input
              placeholder="Свой вопрос к лекции…"
              aria-label="Вопрос к лекции"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <button disabled={!question.trim() || pending}>Спросить</button>
          </form>
        </>
      ) : (
        <p className="muted" style={{ padding: 16 }}>
          Заработает, когда лекция будет расшифрована.
        </p>
      )}
    </section>
  );
}

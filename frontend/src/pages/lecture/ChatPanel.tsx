import { ArrowUp, Sparkles } from 'lucide-react';
import { type FormEvent, useEffect, useRef, useState } from 'react';

import { messageForCode, streamEvents } from '../../api/client';
import type { ChatMessage, SearchHit } from '../../api/types';
import { Markdown } from '../../components/Markdown';
import { timecode } from '../../lib/format';

type Turn = ChatMessage & { sources?: SearchHit[]; error?: boolean; streaming?: boolean };

const SUGGESTIONS = [
  'О чём эта лекция в двух словах?',
  'Какие определения здесь даются?',
  'Объясни самое сложное место попроще',
];

function Wave({ active }: { active: boolean }) {
  const heights = [10, 18, 12, 24, 16, 28, 14, 22, 10, 18, 26, 12];

  return (
    <div className={`wave${active ? ' active' : ''}`} aria-hidden>
      {heights.map((h, i) => (
        <span key={i} style={{ height: h, animationDelay: `${i * 0.08}s` }} />
      ))}
    </div>
  );
}

export function ChatPanel({
  lectureId,
  enabled,
  onOpenSource,
}: {
  lectureId: string;
  enabled: boolean;
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
    send(question);
  };

  return (
    <div className="panel">
      <div className="assistant-head">
        <span className="assistant-mark">
          <Sparkles size={20} />
        </span>
        <div>
          <h3>AI-помощник</h3>
          <div className="muted" style={{ fontSize: 13 }}>
            {pending ? 'Ищет ответ в лекции…' : 'Отвечает по материалам лекции'}
          </div>
        </div>
        <Wave active={pending} />
      </div>

      {enabled ? (
        <>
          <div ref={log} className="chat">
            {turns.map((turn, index) =>
              turn.role === 'user' ? (
                <div key={index} className="bubble bubble-user">
                  {turn.content}
                </div>
              ) : (
                <div
                  key={index}
                  className="bubble bubble-assistant"
                  style={turn.error ? { color: 'var(--danger)' } : undefined}
                >
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
                    <span className="typing">
                      <span />
                      <span />
                      <span />
                    </span>
                  )}
                  {!turn.streaming && !!turn.sources?.length && (
                    <div className="sources">
                      {turn.sources.map((hit, i) => (
                        <button
                          key={hit.chunk_id}
                          className="time-chip"
                          onClick={() => onOpenSource(hit)}
                          title={hit.text}
                        >
                          [{i + 1}] {timecode(hit.start_seconds)}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ),
            )}
          </div>

          {!turns.length && (
            <div className="suggestions">
              {SUGGESTIONS.map((text) => (
                <button key={text} onClick={() => send(text)}>
                  {text}
                </button>
              ))}
            </div>
          )}

          <form className="chat-form" onSubmit={submit}>
            <input
              className="input"
              placeholder="Спросите о лекции…"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <button className="btn btn-primary btn-icon" disabled={!question.trim() || pending} aria-label="Спросить">
              <ArrowUp size={18} />
            </button>
          </form>
        </>
      ) : (
        <p className="muted" style={{ padding: '0 18px 18px', fontSize: 14 }}>
          Помощник заработает, когда лекция будет расшифрована.
        </p>
      )}
    </div>
  );
}

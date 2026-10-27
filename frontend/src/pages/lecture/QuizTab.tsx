import { Check, GraduationCap, RotateCcw, Sparkles, X } from 'lucide-react';
import { useState } from 'react';

import { useGenerateQuiz, useQuiz } from '../../api/hooks';
import type { Lecture, QuizQuestion } from '../../api/types';
import { Empty, Spinner, useToast } from '../../components/ui';
import { timecode } from '../../lib/format';

const LETTERS = ['А', 'Б', 'В', 'Г', 'Д'];

export function QuizTab({
  lecture,
  signedIn,
  onSeek,
}: {
  lecture: Lecture;
  signedIn: boolean;
  onSeek: (seconds: number) => void;
}) {
  const toast = useToast();
  const quiz = useQuiz(lecture);
  const generate = useGenerateQuiz(lecture.id);
  // Chosen option per question index, tied to the quiz version it was given
  // for: a regenerated quiz starts unanswered.
  const [picks, setPicks] = useState<{ version: number; chosen: Record<number, number> }>({
    version: 0,
    chosen: {},
  });
  const questions = quiz.data?.questions ?? [];
  const chosen = picks.version === quiz.dataUpdatedAt ? picks.chosen : {};
  const choose = (index: number, option: number) =>
    setPicks((current) => ({
      version: quiz.dataUpdatedAt,
      chosen: { ...(current.version === quiz.dataUpdatedAt ? current.chosen : {}), [index]: option },
    }));

  const run = () =>
    generate.mutate(undefined, {
      onError: (error) => toast(error.message, { error: true }),
    });

  if (lecture.status !== 'ready') {
    return (
      <Empty icon={<GraduationCap size={22} />} title="Тест появится после обработки">
        Вопросы составляются по расшифровке, а она ещё не готова.
      </Empty>
    );
  }

  if (generate.isPending) {
    return (
      <Empty icon={<Spinner />} title="Составляем вопросы">
        Языковая модель читает лекцию и придумывает вопросы с вариантами ответа. Обычно это меньше минуты.
      </Empty>
    );
  }

  if (quiz.isPending) {
    return <Spinner />;
  }

  if (!questions.length) {
    return (
      <Empty
        icon={<GraduationCap size={22} />}
        title="Проверьте себя"
        action={
          signedIn && (
            <button className="btn btn-primary btn-sm" onClick={run}>
              <Sparkles size={14} /> Составить тест
            </button>
          )
        }
      >
        {signedIn
          ? 'Несколько вопросов по лекции с вариантами ответа. После ответа покажем пояснение и момент видео, где об этом говорят.'
          : 'Войдите, чтобы составить тест по этой лекции.'}
      </Empty>
    );
  }

  const answered = Object.keys(chosen).length;
  const correct = questions.filter((question, index) => chosen[index] === question.answer).length;
  const finished = answered === questions.length;

  return (
    <div className="quiz">
      <div className="quiz-head">
        <span className="label muted">
          {finished ? 'Результат' : `Отвечено ${answered} из ${questions.length}`}
        </span>
        {finished && (
          <span className="quiz-score">
            {correct} <span className="muted">/ {questions.length}</span>
          </span>
        )}
      </div>

      {questions.map((question, index) => (
        <QuestionCard
          key={`${quiz.dataUpdatedAt}-${index}`}
          number={index + 1}
          question={question}
          chosen={chosen[index] ?? -1}
          onChoose={(option) => choose(index, option)}
          onSeek={onSeek}
        />
      ))}

      <div className="quiz-actions">
        <button className="btn btn-sm" onClick={() => setPicks({ version: 0, chosen: {} })} disabled={!answered}>
          <RotateCcw size={14} /> Пройти заново
        </button>
        {signedIn && (
          <button className="btn btn-ghost btn-sm" onClick={run}>
            <Sparkles size={14} /> Другие вопросы
          </button>
        )}
      </div>
    </div>
  );
}

function QuestionCard({
  number,
  question,
  chosen,
  onChoose,
  onSeek,
}: {
  number: number;
  question: QuizQuestion;
  /** -1 until answered. */
  chosen: number;
  onChoose: (option: number) => void;
  onSeek: (seconds: number) => void;
}) {
  const answered = chosen !== -1;
  const right = chosen === question.answer;

  return (
    <div className="quiz-question">
      <div className="quiz-q">
        <span className="chapter-num">{String(number).padStart(2, '0')}</span>
        <span>{question.question}</span>
      </div>

      <div className="quiz-options">
        {question.options.map((option, index) => {
          const state = !answered
            ? ''
            : index === question.answer
              ? ' correct'
              : index === chosen
                ? ' wrong'
                : ' dim';

          return (
            <button
              key={index}
              className={`quiz-option${state}`}
              disabled={answered}
              onClick={() => onChoose(index)}
            >
              <span className="quiz-letter">
                {answered && index === question.answer ? (
                  <Check size={14} />
                ) : answered && index === chosen ? (
                  <X size={14} />
                ) : (
                  LETTERS[index]
                )}
              </span>
              <span>{option}</span>
            </button>
          );
        })}
      </div>

      {answered && (
        <div className={`quiz-feedback${right ? ' correct' : ' wrong'}`}>
          <b>{right ? 'Верно.' : 'Неверно.'}</b> {question.explanation}
          {question.start_seconds != null && (
            <button className="time-chip" onClick={() => onSeek(question.start_seconds!)}>
              ▶ ответ на {timecode(question.start_seconds)}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

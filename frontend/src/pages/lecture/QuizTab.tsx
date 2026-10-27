import { Check, GraduationCap, RotateCcw, Sparkles, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { useGenerateQuiz, useQuiz, useSaveQuizAttempt } from '../../api/hooks';
import type { Lecture, QuizAttempt, QuizQuestion } from '../../api/types';
import { Empty, Spinner, useToast } from '../../components/ui';
import { relativeDate, timecode } from '../../lib/format';

const LETTERS = ['А', 'Б', 'В', 'Г', 'Д'];

interface Picks {
  /** The quiz version (its fetch time) the answers were given for. */
  version: number;
  chosen: Record<number, number>;
  /** All questions answered and sent. */
  saved: boolean;
}

export function QuizTab({
  lecture,
  signedIn,
  canManage,
  attempt,
  onSeek,
}: {
  lecture: Lecture;
  signedIn: boolean;
  canManage: boolean;
  /** The user's saved answers, if they took this quiz before. */
  attempt: QuizAttempt | null | undefined;
  onSeek: (seconds: number) => void;
}) {
  const toast = useToast();
  const quiz = useQuiz(lecture);
  const generate = useGenerateQuiz(lecture.id);
  const save = useSaveQuizAttempt(lecture.id);
  const [picks, setPicks] = useState<Picks>({ version: 0, chosen: {}, saved: true });
  const questions = quiz.data?.questions ?? [];
  const version = quiz.dataUpdatedAt;
  // Until the user touches this quiz, show the answers they saved earlier.
  const restored = attempt?.answers.length === questions.length ? { ...attempt.answers } : {};
  const current: Picks =
    picks.version === version ? picks : { version, chosen: restored, saved: true };
  const chosen = current.chosen;
  const answered = Object.keys(chosen).length;
  const finished = questions.length > 0 && answered === questions.length;

  const choose = (index: number, option: number) =>
    setPicks((previous) => {
      const base = previous.version === version ? previous.chosen : restored;
      return { version, chosen: { ...base, [index]: option }, saved: false };
    });

  useEffect(() => {
    if (!signedIn || !finished || current.saved) return;

    setPicks({ ...current, saved: true });
    save.mutate(
      questions.map((_, index) => chosen[index]!),
      { onError: (error) => toast(error.message, { error: true }) },
    );
  });

  const run = () => {
    if (questions.length && !window.confirm('Составить новый тест? Ответы учеников на текущий будут сброшены.')) {
      return;
    }

    generate.mutate(undefined, {
      onError: (error) => toast(error.message, { error: true }),
    });
  };

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
        title={canManage ? 'Составьте тест для студентов' : 'Теста пока нет'}
        action={
          canManage && (
            <button className="btn btn-primary btn-sm" onClick={run}>
              <Sparkles size={14} /> Составить тест
            </button>
          )
        }
      >
        {canManage
          ? 'Модель составит вопросы с вариантами по расшифровке. Студенты увидят тест сразу, а вы — кто как ответил.'
          : 'Преподаватель ещё не составил тест по этой лекции.'}
      </Empty>
    );
  }

  const correct = questions.filter((question, index) => chosen[index] === question.answer).length;

  return (
    <div className="quiz">
      <div className="quiz-head">
        <span className="label muted">
          {!finished
            ? `Отвечено ${answered} из ${questions.length}`
            : !signedIn
              ? 'Результат · войдите, чтобы сохранить'
              : save.isPending
                ? 'Сохраняем результат'
                : attempt
                  ? `Результат сохранён · ${relativeDate(attempt.updated_at)}`
                  : 'Результат'}
        </span>
        {finished && (
          <span className="quiz-score">
            {correct} <span className="muted">/ {questions.length}</span>
          </span>
        )}
      </div>

      {questions.map((question, index) => (
        <QuestionCard
          key={`${version}-${index}`}
          number={index + 1}
          question={question}
          chosen={chosen[index] ?? -1}
          onChoose={(option) => choose(index, option)}
          onSeek={onSeek}
        />
      ))}

      <div className="quiz-actions">
        <button
          className="btn btn-sm"
          onClick={() => setPicks({ version, chosen: {}, saved: true })}
          disabled={!answered}
        >
          <RotateCcw size={14} /> Пройти заново
        </button>
        {canManage && (
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

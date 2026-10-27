import { useLectureStats, useQuizStats } from '../../api/hooks';
import { Avatar, Bar, Spinner } from '../../components/ui';
import { fullName, relativeDate } from '../../lib/format';

const LETTERS = ['А', 'Б', 'В', 'Г', 'Д'];

const percent = (share: number | null | undefined) => (share == null ? '—' : `${Math.round(share * 100)}%`);

/** For the lecture's teacher: how students watch it and how they did on the quiz. */
export function StatsTab({ lectureId }: { lectureId: string }) {
  const stats = useLectureStats(lectureId);
  const quiz = useQuizStats(lectureId, true);

  if (stats.isPending) {
    return <Spinner />;
  }

  const s = stats.data;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
      <div className="stats lecture-stats">
        <Stat value={s?.viewers} label="смотрели" />
        <Stat value={s?.completed} label="досмотрели" />
        <Stat value={percent(s?.average_watched_share)} label="в среднем досмотрено" />
        <Stat value={s?.likes} label="лайков" />
        <Stat value={s?.comments} label="комментариев" />
        <Stat value={s?.favorites} label="в избранном" />
        <Stat value={s?.quiz_attempts} label="прошли тест" />
        <Stat value={percent(s?.quiz_average_share)} label="верных ответов" />
      </div>

      <section>
        <h3 className="section-label">Тест по вопросам</h3>
        {quiz.isPending ? (
          <Spinner />
        ) : !quiz.data?.questions.length ? (
          <p className="muted">Теста пока нет — составьте его на вкладке «Тест».</p>
        ) : !quiz.data.attempts ? (
          <p className="muted">Тест ещё никто не прошёл.</p>
        ) : (
          quiz.data.questions.map((question, index) => (
            <div key={index} className="quiz-stat">
              <div className="quiz-q">
                <span className="chapter-num">{String(index + 1).padStart(2, '0')}</span>
                <span>{question.question}</span>
                <span className="quiz-stat-share">{percent(question.correct_share)}</span>
              </div>
              {question.options.map((option, optionIndex) => (
                <div key={optionIndex} className={`quiz-stat-option${optionIndex === question.answer ? ' correct' : ''}`}>
                  <span className="quiz-letter">{LETTERS[optionIndex]}</span>
                  <span className="quiz-stat-text">{option}</span>
                  <span className="quiz-stat-bar">
                    <Bar value={question.option_counts[optionIndex]! / quiz.data.attempts} brand={optionIndex === question.answer} />
                  </span>
                  <span className="quiz-stat-count">{question.option_counts[optionIndex]}</span>
                </div>
              ))}
            </div>
          ))
        )}
      </section>

      {!!quiz.data?.students.length && (
        <section>
          <h3 className="section-label">Студенты</h3>
          {quiz.data.students.map((result) => (
            <div key={result.user.id} className="student-result">
              <Avatar user={result.user} size={32} />
              <span className="student-name">{fullName(result.user)}</span>
              <span className="muted">{relativeDate(result.updated_at)}</span>
              <span className="student-score">
                {result.correct}
                <span className="muted"> / {result.total}</span>
              </span>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

function Stat({ value, label }: { value: number | string | undefined; label: string }) {
  return (
    <div className="stat">
      <span className="stat-value">{value ?? '—'}</span>
      <span className="stat-label">{label}</span>
    </div>
  );
}

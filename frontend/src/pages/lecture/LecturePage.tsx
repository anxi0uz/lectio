import { FileText, Heart, Link2, RefreshCw, ThumbsUp, Trash2 } from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router';

import {
  isProcessing,
  isSearchable,
  saveProgress,
  useBookmarkActions,
  useComments,
  useCourse,
  useEnrollment,
  useLecture,
  useLectureActions,
  useLectureState,
  useLectureStats,
  useLectures,
  useSegments,
  useSummary,
  useToggleFavorite,
  useToggleLike,
  useUser,
} from '../../api/hooks';
import type { SearchHit } from '../../api/types';
import { useAuth } from '../../auth/AuthProvider';
import { Avatar, Empty, Skeleton, useToast } from '../../components/ui';
import { fullName, timecode } from '../../lib/format';
import { ChatPanel } from './ChatPanel';
import { CourseContent } from './CourseContent';
import { DiscussionTab } from './DiscussionTab';
import { Player } from './Player';
import { ProcessingCard } from './ProcessingCard';
import { QuizTab } from './QuizTab';
import { StatsTab } from './StatsTab';
import { BookmarksTab, ChaptersTab, SummaryTab, TermsTab, TranscriptTab } from './Tabs';
import { NowSpeaking } from './TranscriptPanel';

type Tab = 'summary' | 'chapters' | 'terms' | 'quiz' | 'transcript' | 'notes' | 'discussion' | 'stats';

const PROGRESS_SAVE_MS = 10_000;
const LANGUAGES: Record<string, string> = { ru: 'Русский', en: 'English' };

export function LecturePage() {
  const { id = '' } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { user } = useAuth();

  const lectureQuery = useLecture(id);
  const lecture = lectureQuery.data;
  const { data: segments = [] } = useSegments(lecture);
  const { data: summary } = useSummary(lecture);
  const { data: state } = useLectureState(id);
  const { data: course } = useCourse(lecture?.course_id);
  const { data: owner } = useUser(lecture?.owner_id);
  const { data: courseLectures = [] } = useLectures({ courseId: lecture?.course_id ?? undefined });
  const actions = useLectureActions(id);
  const favorite = useToggleFavorite(id);
  const like = useToggleLike(id);
  const lectureStats = useLectureStats(id);
  const comments = useComments(id);
  const bookmarks = useBookmarkActions(id);
  const enrollment = useEnrollment(lecture?.course_id ?? '');

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [tab, setTab] = useState<Tab>('summary');
  const resumed = useRef(false);

  const canManage = state?.can_manage ?? false;
  const chapters = summary?.chapters ?? [];
  const terms = summary?.key_terms ?? [];
  const lectureBookmarks = state?.bookmarks ?? [];

  const seek = useCallback((seconds: number, play = true) => {
    const video = videoRef.current;
    if (!video) return;

    video.currentTime = seconds;
    setTime(seconds);
    if (play) void video.play();
    video.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, []);

  // Jump to ?t= from search results, otherwise resume where the user left.
  const onLoaded = useCallback(() => {
    if (resumed.current) return;
    resumed.current = true;

    const fromUrl = params.get('t');
    if (fromUrl !== null) {
      seek(Number(fromUrl), false);
      return;
    }

    const position = state?.progress.position_seconds ?? 0;
    if (position > 5 && !state?.progress.completed) {
      seek(position, false);
      toast(`Продолжаем с ${timecode(position)}`);
    }
  }, [params, seek, state, toast]);

  useEffect(() => {
    resumed.current = false;
    setTime(0);
    setTab('summary');
  }, [id]);

  // A later ?t= (e.g. a citation link to the same lecture) seeks directly.
  useEffect(() => {
    const t = params.get('t');
    if (t !== null && resumed.current && videoRef.current) seek(Number(t));
  }, [params, seek]);

  // Save the position while playing and when leaving the page.
  useEffect(() => {
    if (!user || !lecture?.video_url) return;

    const save = () => {
      const video = videoRef.current;
      if (video && video.currentTime > 1) {
        void saveProgress(id, video.currentTime).catch(() => undefined);
      }
    };

    const interval = playing ? window.setInterval(save, PROGRESS_SAVE_MS) : undefined;
    if (!playing) save();

    return () => {
      window.clearInterval(interval);
      if (playing) save();
    };
  }, [playing, user, id, lecture?.video_url]);

  const openSource = useCallback(
    (hit: SearchHit) => {
      if (hit.lecture_id === id) seek(hit.start_seconds);
      else navigate(`/lectures/${hit.lecture_id}?t=${Math.floor(hit.start_seconds)}`);
    },
    [id, navigate, seek],
  );

  const addBookmark = useCallback(() => {
    if (!user) {
      toast('Войдите, чтобы ставить закладки', { error: true });
      return;
    }

    bookmarks.create.mutate(
      { position_seconds: Math.floor(videoRef.current?.currentTime ?? 0) },
      {
        onSuccess: (bookmark) => toast(`Закладка на ${timecode(bookmark.position_seconds)}`),
        onError: (error) => toast(error.message, { error: true }),
      },
    );
  }, [user, bookmarks.create, toast]);

  const tabs = useMemo(
    () =>
      [
        { key: 'summary', label: 'Конспект' },
        { key: 'chapters', label: 'Оглавление', count: chapters.length },
        { key: 'terms', label: 'Термины', count: terms.length },
        { key: 'quiz', label: 'Тест' },
        { key: 'transcript', label: 'Расшифровка' },
        { key: 'notes', label: 'Мои заметки', count: lectureBookmarks.length },
        { key: 'discussion', label: 'Обсуждение', count: comments.data?.length },
        ...(canManage ? [{ key: 'stats', label: 'Статистика' }] : []),
      ] as { key: Tab; label: string; count?: number }[],
    [chapters.length, terms.length, lectureBookmarks.length, comments.data?.length, canManage],
  );

  if (lectureQuery.isError) {
    return (
      <div className="card">
        <Empty
          icon={<FileText size={22} />}
          title="Лекция не найдена"
          action={
            <Link to="/lectures" className="btn btn-sm">
              Ко всем лекциям
            </Link>
          }
        >
          Возможно, её удалили или ссылка неверная.
        </Empty>
      </div>
    );
  }

  if (!lecture) {
    return (
      <div className="page">
        <div className="page-header">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <Skeleton width={220} height={14} />
            <Skeleton width="70%" height={56} />
          </div>
        </div>
        <div className="card lecture-layout">
          <div className="lecture-main">
            <Skeleton height={420} />
          </div>
          <div className="lecture-aside">
            <Skeleton height={200} />
          </div>
        </div>
      </div>
    );
  }

  const searchable = isSearchable(lecture);
  const processing = isProcessing(lecture);

  const share = async () => {
    const url = new URL(`/lectures/${id}`, window.location.origin);
    if (time > 1) url.searchParams.set('t', String(Math.floor(time)));
    await navigator.clipboard.writeText(url.toString());
    toast(time > 1 ? `Ссылка на момент ${timecode(time)} скопирована` : 'Ссылка скопирована');
  };

  const order = [...courseLectures].reverse().findIndex((item) => item.id === id);
  const watched = state?.progress.completed
    ? 1
    : lecture.duration_seconds
      ? (state?.progress.position_seconds ?? 0) / lecture.duration_seconds
      : 0;

  return (
    <div className="page">
      <section className="page-header">
        <div style={{ minWidth: 0 }}>
          <div className="eyebrow">
            {course ? <Link to={`/courses/${course.id}`}>{course.title}</Link> : <Link to="/lectures">Все лекции</Link>}
            {course && order >= 0 && (
              <span className="accent">
                Лекция {String(order + 1).padStart(2, '0')} / {String(courseLectures.length).padStart(2, '0')}
              </span>
            )}
            {lecture.language && <span>{LANGUAGES[lecture.language] ?? lecture.language}</span>}
          </div>
          <h1>{lecture.title}</h1>
          <div className="actions" style={{ marginTop: 24 }}>
            <button className="btn btn-primary" onClick={share}>
              <Link2 size={16} /> {time > 1 ? `Поделиться моментом ${timecode(time)}` : 'Поделиться'}
            </button>
            {user && (
              <button
                className={`btn${state?.is_favorite ? ' btn-active' : ''}`}
                onClick={() => favorite.mutate(!state?.is_favorite)}
              >
                <Heart size={16} fill={state?.is_favorite ? 'currentColor' : 'none'} />
                {state?.is_favorite ? 'В избранном' : 'В избранное'}
              </button>
            )}
            {user ? (
              <button
                className={`btn${state?.is_liked ? ' btn-active' : ''}`}
                onClick={() => like.mutate(!state?.is_liked)}
                aria-label={state?.is_liked ? 'Убрать лайк' : 'Нравится'}
              >
                <ThumbsUp size={16} fill={state?.is_liked ? 'currentColor' : 'none'} />
                {lectureStats.data?.likes ?? 0}
              </button>
            ) : (
              !!lectureStats.data?.likes && (
                <span className="btn" aria-label="Лайки" style={{ cursor: 'default' }}>
                  <ThumbsUp size={16} /> {lectureStats.data.likes}
                </span>
              )
            )}
            {course && user && !state?.is_enrolled_in_course && (
              <button className="btn" onClick={() => enrollment.enroll.mutate()} disabled={enrollment.enroll.isPending}>
                Записаться на курс
              </button>
            )}
          </div>
        </div>

        <dl className="facts">
          <div>
            <dt>Длина</dt>
            <dd>{timecode(lecture.duration_seconds)}</dd>
          </div>
          <div>
            <dt>Разделы</dt>
            <dd>{chapters.length || '—'}</dd>
          </div>
          <div>
            <dt>{user ? 'Пройдено' : 'Термины'}</dt>
            <dd className="accent">{user ? `${Math.round(watched * 100)}%` : terms.length || '—'}</dd>
          </div>
        </dl>
      </section>

      {(processing || lecture.status === 'failed') && (
        <ProcessingCard
          lecture={lecture}
          canManage={canManage}
          onRetry={() => actions.reprocess.mutate()}
          retrying={actions.reprocess.isPending}
        />
      )}

      <section className="card lecture-layout">
        <div className="lecture-main">
          <Player
            videoRef={videoRef}
            src={lecture.video_url}
            duration={lecture.duration_seconds}
            segments={segments}
            chapterStarts={chapters.map((c) => c.start_seconds)}
            bookmarkMarks={lectureBookmarks.map((b) => b.position_seconds)}
            time={time}
            onTime={setTime}
            onPlayingChange={setPlaying}
            onLoaded={onLoaded}
            onBookmark={addBookmark}
            placeholder={
              lecture.status === 'failed' ? (
                <>
                  <b>Видео не загрузилось</b>
                  <span>Причина и кнопка повтора — выше</span>
                </>
              ) : (
                <>
                  <b>Видео скачивается</b>
                  <span>Оно появится здесь, как только загрузка завершится</span>
                </>
              )
            }
          />

          <div className="tabs" role="tablist">
            {tabs.map((item) => (
              <button
                key={item.key}
                role="tab"
                aria-selected={tab === item.key}
                className={`tab${tab === item.key ? ' active' : ''}`}
                onClick={() => setTab(item.key)}
              >
                {item.label}
                {!!item.count && <span className="tab-count">{item.count}</span>}
              </button>
            ))}
          </div>

          <div>
            {tab === 'summary' && (
              <SummaryTab
                summary={summary}
                processing={processing}
                canManage={canManage}
                onRegenerate={() =>
                  actions.resummarize.mutate(undefined, {
                    onSuccess: () => toast('Конспект поставлен в очередь'),
                    onError: (error) => toast(error.message, { error: true }),
                  })
                }
                regenerating={actions.resummarize.isPending}
              />
            )}
            {tab === 'chapters' && <ChaptersTab chapters={chapters} time={time} onSeek={seek} />}
            {tab === 'terms' && <TermsTab terms={terms} onSeek={seek} />}
            {tab === 'quiz' && (
              <QuizTab
                lecture={lecture}
                signedIn={!!user}
                canManage={canManage}
                attempt={state?.quiz_attempt}
                onSeek={seek}
              />
            )}
            {tab === 'transcript' && (
              <TranscriptTab lectureId={id} segments={segments} time={time} onSeek={seek} />
            )}
            {tab === 'notes' && (
              <BookmarksTab
                lectureId={id}
                bookmarks={lectureBookmarks}
                time={time}
                signedIn={!!user}
                onSeek={seek}
              />
            )}
            {tab === 'discussion' && (
              <DiscussionTab lectureId={id} user={user} canManage={canManage} time={time} onSeek={seek} />
            )}
            {tab === 'stats' && canManage && <StatsTab lectureId={id} />}
          </div>

          {owner && (
            <div className="list-item" style={{ borderTop: '1px solid var(--line)' }}>
              <Avatar user={owner} size={44} />
              <div>
                <div className="label muted">Преподаватель</div>
                <div style={{ fontFamily: 'var(--display)', fontWeight: 700, fontSize: 20, letterSpacing: '-0.02em' }}>
                  {fullName(owner)}
                </div>
              </div>
            </div>
          )}

          {canManage && (
            <div className="actions" style={{ borderTop: '1px solid var(--hair)', paddingTop: 16 }}>
              <span className="label muted" style={{ alignSelf: 'center', marginRight: 8 }}>Управление</span>
              <button
                className="btn btn-sm"
                disabled={!searchable || actions.resummarize.isPending}
                onClick={() =>
                  actions.resummarize.mutate(undefined, {
                    onSuccess: () => toast('Конспект поставлен в очередь'),
                    onError: (error) => toast(error.message, { error: true }),
                  })
                }
              >
                <FileText size={14} /> Пересобрать конспект
              </button>
              <button
                className="btn btn-sm"
                disabled={processing || actions.reprocess.isPending}
                onClick={() => actions.reprocess.mutate()}
              >
                <RefreshCw size={14} /> Обработать заново
              </button>
              <button
                className="btn btn-sm btn-danger"
                onClick={() => {
                  if (!window.confirm('Удалить лекцию вместе с видео и расшифровкой?')) return;
                  actions.remove.mutate(undefined, {
                    onSuccess: () => {
                      toast('Лекция удалена');
                      navigate('/lectures');
                    },
                  });
                }}
              >
                <Trash2 size={14} /> Удалить
              </button>
            </div>
          )}
        </div>

        <aside className="lecture-aside">
          <NowSpeaking segments={segments} time={time} onSeek={seek} />
          <ChatPanel lectureId={id} enabled={searchable} chapters={chapters} onOpenSource={openSource} />
          {course && <CourseContent course={course} currentId={id} />}
        </aside>
      </section>
    </div>
  );
}

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import { useEffect, useRef } from 'react';

import { useAuth } from '../auth/AuthProvider';
import { ApiError, api, refreshSession, uploadWithProgress } from './client';
import type {
  Bookmark,
  BookmarkWithLecture,
  Comment,
  Course,
  Dashboard,
  EnrolledCourse,
  GlossaryEntry,
  Leaderboard,
  Lecture,
  LectureState,
  LectureStats,
  MyAchievements,
  Progress,
  Quiz,
  QuizAttempt,
  QuizStats,
  PublicUser,
  RecentSearch,
  SearchHit,
  Segment,
  Summary,
} from './types';

const IN_PROGRESS = new Set([
  'pending',
  'downloading',
  'extracting_audio',
  'transcribing',
  'indexing',
  'summarizing',
]);

export const isProcessing = (lecture?: Lecture | null) =>
  !!lecture && IN_PROGRESS.has(lecture.status);

export const isSearchable = (lecture?: Lecture | null) =>
  !!lecture && (lecture.status === 'ready' || lecture.status === 'summarizing');

/* ---------- lectures ---------- */

export function useLectures(params: { courseId?: string; ownerId?: string } = {}) {
  const search = new URLSearchParams({ limit: '200' });
  if (params.courseId) search.set('course_id', params.courseId);
  if (params.ownerId) search.set('owner_id', params.ownerId);

  return useQuery({
    queryKey: ['lectures', params],
    queryFn: () => api<Lecture[]>(`/lectures?${search}`),
    // Keep cards' processing status fresh while anything is in the works.
    refetchInterval: (query) =>
      query.state.data?.some(isProcessing) ? 3000 : false,
  });
}

export function useLecture(id: string | undefined) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ['lecture', id],
    queryFn: () => api<Lecture>(`/lectures/${id}`),
    enabled: !!id,
    refetchInterval: (query) => (isProcessing(query.state.data) ? 2000 : false),
    // People switch tabs while a lecture is processed for minutes.
    refetchIntervalInBackground: true,
  });
  const status = query.data?.status;
  const previous = useRef(status);

  // Each stage brings new data: the transcript after indexing, the summary
  // and contents when it is ready, a fresh transcript after reprocessing.
  useEffect(() => {
    if (!id || !status || previous.current === status) return;

    const first = previous.current === undefined;
    previous.current = status;
    if (first) return;

    for (const key of ['segments', 'summary', 'quiz', 'lecture-stats']) {
      client.invalidateQueries({ queryKey: [key, id] });
    }
    client.invalidateQueries({ queryKey: ['lectures'] });
  }, [client, id, status]);

  return query;
}

export function useSegments(lecture: Lecture | undefined) {
  return useQuery({
    queryKey: ['segments', lecture?.id],
    queryFn: () => api<Segment[]>(`/lectures/${lecture!.id}/segments`),
    enabled: isSearchable(lecture),
    staleTime: Infinity,
  });
}

export function useSummary(lecture: Lecture | undefined) {
  return useQuery({
    queryKey: ['summary', lecture?.id],
    queryFn: () => api<Summary>(`/lectures/${lecture!.id}/summary`),
    enabled: isSearchable(lecture),
  });
}

export function useQuiz(lecture: Lecture | undefined) {
  return useQuery({
    queryKey: ['quiz', lecture?.id],
    queryFn: () => api<Quiz>(`/lectures/${lecture!.id}/quiz`),
    enabled: lecture?.status === 'ready',
  });
}

export function useGenerateQuiz(id: string) {
  const client = useQueryClient();

  return useMutation({
    mutationFn: () => api<Quiz>(`/lectures/${id}/quiz`, { method: 'POST' }),
    onSuccess: (quiz) => {
      client.setQueryData(['quiz', id], quiz);
      // A new quiz drops everyone's answers.
      client.invalidateQueries({ queryKey: ['lecture-state', id] });
      client.invalidateQueries({ queryKey: ['quiz-stats', id] });
      client.invalidateQueries({ queryKey: ['lecture-stats', id] });
    },
  });
}

export function useSaveQuizAttempt(id: string) {
  const client = useQueryClient();

  return useMutation({
    mutationFn: (answers: number[]) =>
      api<QuizAttempt>(`/lectures/${id}/quiz/attempt`, { method: 'PUT', body: { answers } }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['lecture-state', id] });
      client.invalidateQueries({ queryKey: ['quiz-stats', id] });
      client.invalidateQueries({ queryKey: ['lecture-stats', id] });
    },
  });
}

export function useQuizStats(id: string, enabled: boolean) {
  return useQuery({
    queryKey: ['quiz-stats', id],
    queryFn: () => api<QuizStats>(`/lectures/${id}/quiz/stats`),
    enabled,
  });
}

export function useLectureStats(id: string) {
  return useQuery({
    queryKey: ['lecture-stats', id],
    queryFn: () => api<LectureStats>(`/lectures/${id}/stats`),
  });
}

export function useToggleLike(id: string) {
  const client = useQueryClient();

  return useMutation({
    mutationFn: (liked: boolean) => api<null>(`/lectures/${id}/like`, { method: liked ? 'PUT' : 'DELETE' }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['lecture-state', id] });
      client.invalidateQueries({ queryKey: ['lecture-stats', id] });
    },
  });
}

export function useComments(id: string) {
  return useQuery({
    queryKey: ['comments', id],
    queryFn: () => api<Comment[]>(`/lectures/${id}/comments`),
  });
}

export function useCommentActions(id: string) {
  const client = useQueryClient();
  const refresh = () => {
    client.invalidateQueries({ queryKey: ['comments', id] });
    client.invalidateQueries({ queryKey: ['lecture-stats', id] });
  };

  return {
    create: useMutation({
      mutationFn: (body: { text: string; position_seconds?: number }) =>
        api<Comment>(`/lectures/${id}/comments`, { method: 'POST', body }),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: (commentId: string) => api<null>(`/lectures/${id}/comments/${commentId}`, { method: 'DELETE' }),
      onSuccess: refresh,
    }),
  };
}

export function useLectureState(id: string | undefined) {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['lecture-state', id, user?.id],
    queryFn: () => api<LectureState>(`/lectures/${id}/me`),
    enabled: !!id && !!user,
  });
}

export function useUser(id: string | null | undefined) {
  return useQuery({
    queryKey: ['user', id],
    queryFn: () => api<PublicUser>(`/users/${id}`),
    enabled: !!id,
    staleTime: Infinity,
    retry: false,
  });
}

export function useUploadLecture() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: async ({
      form,
      onProgress,
    }: {
      form: FormData;
      onProgress: (fraction: number) => void;
    }) => {
      try {
        return await uploadWithProgress<Lecture>('/lectures', form, onProgress);
      } catch (error) {
        // The access token may have expired during a long upload.
        if (error instanceof ApiError && error.status === 401 && (await refreshSession())) {
          return uploadWithProgress<Lecture>('/lectures', form, onProgress);
        }
        throw error;
      }
    },
    onSuccess: () => client.invalidateQueries({ queryKey: ['lectures'] }),
  });
}

export function useImportLecture() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: (body: { url: string; title?: string; course_id?: string; allow_duplicate?: boolean }) =>
      api<Lecture>('/lectures/import', { method: 'POST', body }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['lectures'] }),
  });
}

export function useLectureActions(id: string) {
  const client = useQueryClient();
  const refresh = () => {
    client.invalidateQueries({ queryKey: ['lecture', id] });
    client.invalidateQueries({ queryKey: ['lectures'] });
  };

  return {
    reprocess: useMutation({
      mutationFn: () => api<Lecture>(`/lectures/${id}/reprocess`, { method: 'POST' }),
      onSuccess: refresh,
    }),
    resummarize: useMutation({
      mutationFn: () => api<null>(`/lectures/${id}/summary`, { method: 'POST' }),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: () => api<null>(`/lectures/${id}`, { method: 'DELETE' }),
      onSuccess: () => client.invalidateQueries({ queryKey: ['lectures'] }),
    }),
    update: useMutation({
      mutationFn: (body: { title?: string; course_id?: string | null }) =>
        api<Lecture>(`/lectures/${id}`, { method: 'PATCH', body }),
      onSuccess: refresh,
    }),
  };
}

/* ---------- glossary ---------- */

export function useGlossary(query: string, courseId: string) {
  const params = new URLSearchParams();
  if (query) params.set('q', query);
  if (courseId) params.set('course_id', courseId);

  return useQuery({
    queryKey: ['glossary', query, courseId],
    queryFn: () => api<GlossaryEntry[]>(`/glossary?${params}`),
    placeholderData: keepPreviousData,
  });
}

/* ---------- courses ---------- */

export function useCourses() {
  return useQuery({
    queryKey: ['courses'],
    queryFn: () => api<Course[]>('/courses'),
  });
}

export function useCourse(id: string | null | undefined) {
  return useQuery({
    queryKey: ['course', id],
    queryFn: () => api<Course>(`/courses/${id}`),
    enabled: !!id,
  });
}

export function useMyCourses() {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['my-courses', user?.id],
    queryFn: () => api<EnrolledCourse[]>('/me/courses'),
    enabled: !!user,
  });
}

export function useCreateCourse() {
  const client = useQueryClient();

  return useMutation({
    mutationFn: (body: { title: string; description?: string }) =>
      api<Course>('/courses', { method: 'POST', body }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['courses'] }),
  });
}

export function useEnrollment(courseId: string) {
  const client = useQueryClient();
  const invalidate = () => {
    client.invalidateQueries({ queryKey: ['my-courses'] });
    client.invalidateQueries({ queryKey: ['lecture-state'] });
    client.invalidateQueries({ queryKey: ['dashboard'] });
  };

  return {
    enroll: useMutation({
      mutationFn: () => api<null>(`/courses/${courseId}/enrollment`, { method: 'PUT' }),
      onSuccess: invalidate,
    }),
    leave: useMutation({
      mutationFn: () => api<null>(`/courses/${courseId}/enrollment`, { method: 'DELETE' }),
      onSuccess: invalidate,
    }),
  };
}

/* ---------- search and Q&A ---------- */

export function useSearch(
  query: string,
  scope: { lectureId?: string; courseId?: string } = {},
  limit = 10,
) {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  if (scope.lectureId) params.set('lecture_id', scope.lectureId);
  if (scope.courseId) params.set('course_id', scope.courseId);

  return useQuery({
    queryKey: ['search', query, scope, limit],
    queryFn: ({ signal }) => api<SearchHit[]>(`/search?${params}`, { signal }),
    enabled: query.trim().length > 0,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}

export function useSearchHistory() {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['search-history', user?.id],
    queryFn: () => api<RecentSearch[]>('/me/search-history?limit=8'),
    enabled: !!user,
  });
}

/* ---------- personal ---------- */

export function useDashboard() {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['dashboard', user?.id],
    queryFn: () => api<Dashboard>('/me/dashboard'),
    enabled: !!user,
  });
}

export function useFavorites() {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['favorites', user?.id],
    queryFn: () => api<Lecture[]>('/me/favorites'),
    enabled: !!user,
  });
}

export function useToggleFavorite(lectureId: string) {
  const client = useQueryClient();

  return useMutation({
    mutationFn: (favorite: boolean) =>
      api<null>(`/lectures/${lectureId}/favorite`, {
        method: favorite ? 'PUT' : 'DELETE',
      }),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ['lecture-state', lectureId] });
      client.invalidateQueries({ queryKey: ['favorites'] });
      client.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export function useAllBookmarks() {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['bookmarks', user?.id],
    queryFn: () => api<BookmarkWithLecture[]>('/me/bookmarks'),
    enabled: !!user,
  });
}

export function useBookmarkActions(lectureId?: string) {
  const client = useQueryClient();
  const invalidate = () => {
    client.invalidateQueries({ queryKey: ['lecture-state'] });
    client.invalidateQueries({ queryKey: ['bookmarks'] });
    client.invalidateQueries({ queryKey: ['dashboard'] });
  };

  return {
    create: useMutation({
      mutationFn: (body: { position_seconds: number; note?: string }) =>
        api<Bookmark>(`/lectures/${lectureId}/bookmarks`, { method: 'POST', body }),
      onSuccess: invalidate,
    }),
    update: useMutation({
      mutationFn: ({ id, note }: { id: string; note: string }) =>
        api<Bookmark>(`/bookmarks/${id}`, { method: 'PATCH', body: { note } }),
      onSuccess: invalidate,
    }),
    remove: useMutation({
      mutationFn: (id: string) => api<null>(`/bookmarks/${id}`, { method: 'DELETE' }),
      onSuccess: invalidate,
    }),
  };
}

export function saveProgress(
  lectureId: string,
  positionSeconds: number,
  completed?: boolean,
) {
  return api<Progress>(`/lectures/${lectureId}/progress`, {
    method: 'PUT',
    body: { position_seconds: positionSeconds, completed },
  });
}

/* ---------- gamification ---------- */

export function useMyAchievements() {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['achievements', user?.id],
    queryFn: () => api<MyAchievements>('/me/achievements'),
    enabled: !!user,
  });
}

export function useLeaderboard() {
  const { user } = useAuth();

  return useQuery({
    queryKey: ['leaderboard', user?.id],
    queryFn: () => api<Leaderboard>('/leaderboard'),
    enabled: !!user,
  });
}

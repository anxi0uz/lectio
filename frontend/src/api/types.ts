export type UserRole = 'student' | 'teacher';

export type LectureStatus =
  | 'pending'
  | 'downloading'
  | 'extracting_audio'
  | 'transcribing'
  | 'indexing'
  | 'summarizing'
  | 'ready'
  | 'failed';

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  avatar_url: string | null;
  created_at: string;
}

export interface PublicUser {
  id: string;
  first_name: string;
  last_name: string;
  role: UserRole;
  avatar_url: string | null;
}

export interface AuthResponse {
  access_token: string;
  user: User;
}

export interface Course {
  id: string;
  owner_id: string | null;
  title: string;
  description: string | null;
  created_at: string;
  lectures_count: number;
  total_duration_seconds: number;
}

export interface EnrolledCourse extends Course {
  enrolled_at: string;
  completed_lectures: number;
  progress: number;
}

export interface Lecture {
  id: string;
  course_id: string | null;
  owner_id: string | null;
  title: string;
  source_type: 'upload' | 'url';
  source_url: string | null;
  duration_seconds: number | null;
  language: string | null;
  status: LectureStatus;
  progress: number;
  error: string | null;
  created_at: string;
  updated_at: string;
  video_url: string | null;
  thumbnail_url: string | null;
  subtitles_url: string | null;
}

export interface Segment {
  id: string;
  position: number;
  start_seconds: number;
  end_seconds: number;
  text: string;
}

export interface Chapter {
  id: string;
  title: string;
  start_seconds: number;
  subsections: Chapter[];
}

export interface KeyTerm {
  term: string;
  definition: string;
  start_seconds: number | null;
}

export interface TermMention {
  lecture_id: string;
  lecture_title: string;
  course_id: string | null;
  definition: string;
  start_seconds: number | null;
}

export interface GlossaryEntry {
  term: string;
  mentions: TermMention[];
}

export interface QuizQuestion {
  question: string;
  options: string[];
  /** Index into options. */
  answer: number;
  explanation: string;
  start_seconds: number | null;
}

export interface Quiz {
  lecture_id: string;
  questions: QuizQuestion[];
}

export interface QuizAttempt {
  /** Chosen option index per question. */
  answers: number[];
  correct: number;
  total: number;
  updated_at: string;
}

export interface QuizStats {
  attempts: number;
  average_share: number | null;
  questions: {
    question: string;
    options: string[];
    answer: number;
    option_counts: number[];
    correct_share: number;
  }[];
  students: { user: PublicUser; correct: number; total: number; updated_at: string }[];
}

export interface Summary {
  lecture_id: string;
  status: LectureStatus;
  summary: string | null;
  error: string | null;
  chapters: Chapter[];
  key_terms: KeyTerm[];
  suggested_questions: string[];
}

export interface SearchHit {
  chunk_id: string;
  lecture_id: string;
  lecture_title: string;
  start_seconds: number;
  end_seconds: number;
  text: string;
  highlight: string;
  score: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface Answer {
  answer: string;
  sources: SearchHit[];
}

export interface Progress {
  lecture_id: string;
  position_seconds: number;
  completed: boolean;
  updated_at: string | null;
}

export interface ContinueWatchingItem {
  lecture: Lecture;
  position_seconds: number;
  updated_at: string;
}

export interface Bookmark {
  id: string;
  lecture_id: string;
  position_seconds: number;
  note: string | null;
  created_at: string;
  updated_at: string;
}

export interface BookmarkWithLecture extends Bookmark {
  lecture_title: string;
}

export interface RecentSearch {
  query: string;
  searched_at: string;
}

export interface Dashboard {
  enrolled_courses: number;
  lectures_completed: number;
  lectures_in_progress: number;
  watched_seconds: number;
  favorites: number;
  bookmarks: number;
  lectures_uploaded: number | null;
  continue_watching: ContinueWatchingItem[];
  recent_searches: RecentSearch[];
}

export interface LectureState {
  progress: Progress;
  is_favorite: boolean;
  is_liked: boolean;
  is_enrolled_in_course: boolean;
  can_manage: boolean;
  bookmarks: Bookmark[];
  quiz_attempt: QuizAttempt | null;
}

export interface LectureStats {
  viewers: number;
  completed: number;
  average_watched_share: number | null;
  likes: number;
  comments: number;
  favorites: number;
  bookmarks: number;
  quiz_attempts: number;
  quiz_average_share: number | null;
}

export interface Comment {
  id: string;
  lecture_id: string;
  author: PublicUser;
  text: string;
  position_seconds: number | null;
  created_at: string;
}

export interface Level {
  xp: number;
  level: number;
  /** XP at which the current level started and the next one begins. */
  level_xp: number;
  next_level_xp: number;
}

export interface Achievement {
  id: string;
  title: string;
  description: string;
  progress: number;
  target: number;
  unlocked: boolean;
}

export interface MyAchievements {
  level: Level;
  achievements: Achievement[];
}

export interface LeaderboardEntry {
  rank: number;
  user: PublicUser;
  level: Level;
  achievements: number;
}

export interface Leaderboard {
  top: LeaderboardEntry[];
  me: LeaderboardEntry | null;
}

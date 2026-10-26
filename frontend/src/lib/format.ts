import type { LectureStatus } from '../api/types';

export function timecode(seconds: number | null | undefined): string {
  const total = Math.max(0, Math.floor(seconds ?? 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = String(total % 60).padStart(2, '0');

  return hours
    ? `${hours}:${String(minutes).padStart(2, '0')}:${secs}`
    : `${minutes}:${secs}`;
}

export function duration(seconds: number | null | undefined): string {
  if (!seconds) return '—';

  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${Math.max(minutes, 1)} мин`;

  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} ч ${rest} мин` : `${hours} ч`;
}

export function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;

  if (mod10 === 1 && mod100 !== 11) return `${n} ${one}`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${n} ${few}`;
  return `${n} ${many}`;
}

export const lectures = (n: number) => plural(n, 'лекция', 'лекции', 'лекций');

export const STATUS_LABELS: Record<LectureStatus, string> = {
  pending: 'В очереди',
  downloading: 'Скачивание',
  extracting_audio: 'Извлечение звука',
  transcribing: 'Расшифровка',
  indexing: 'Индексация',
  summarizing: 'Конспект',
  ready: 'Готово',
  failed: 'Ошибка',
};

export const PIPELINE: LectureStatus[] = [
  'downloading',
  'extracting_audio',
  'transcribing',
  'indexing',
  'summarizing',
];

export function fullName(user: { first_name: string; last_name: string }) {
  return `${user.first_name} ${user.last_name}`.trim();
}

export function initials(user: { first_name: string; last_name: string }) {
  return `${user.first_name[0] ?? ''}${user.last_name[0] ?? ''}`.toUpperCase();
}

export function relativeDate(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);

  if (days <= 0) return 'сегодня';
  if (days === 1) return 'вчера';
  if (days < 7) return plural(days, 'день', 'дня', 'дней') + ' назад';

  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' });
}

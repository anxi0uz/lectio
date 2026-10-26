let accessToken = null;
let refreshing = null;
const base = '/api/v1';

export class ApiError extends Error {
  constructor(message, status, requestId) {
    super(message);
    this.status = status;
    this.requestId = requestId;
  }
}
export function setAccessToken(token) {
  accessToken = token;
}
export async function refreshSession() {
  if (!refreshing)
    refreshing = fetch(`${base}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    })
      .then(async (response) => {
        if (!response.ok) {
          accessToken = null;
          return false;
        }
        accessToken = (await response.json()).access_token;
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  return refreshing;
}
export async function api(
  path,
  { method = 'GET', body, signal, retry = true, ...options } = {},
) {
  let response;
  try {
    response = await fetch(`${base}${path}`, {
      ...options,
      method,
      signal,
      credentials: 'include',
      headers: {
        ...(body && !(body instanceof FormData)
          ? { 'Content-Type': 'application/json' }
          : {}),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body:
        body instanceof FormData
          ? body
          : body === undefined
            ? undefined
            : JSON.stringify(body),
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError(
      'Не удалось связаться с сервером. Проверьте, что Lectio API запущен.',
      0,
    );
  }
  if (response.status === 401 && retry && !path.startsWith('/auth/')) {
    if (await refreshSession())
      return api(path, { method, body, signal, retry: false, ...options });
    window.dispatchEvent(new Event('lectio:session-expired'));
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const defaults = {
      401: 'Войдите в аккаунт, чтобы продолжить.',
      403: 'У вас нет прав на это действие.',
      404: 'Материал не найден.',
      409: 'Материал ещё обрабатывается или действие пока недоступно.',
      413: 'Файл слишком большой.',
      415: 'Этот формат файла не поддерживается.',
      429: 'Слишком много попыток. Попробуйте немного позже.',
      503: 'AI-помощник сейчас недоступен. Попробуйте позже.',
    };
    const message = Array.isArray(data?.detail)
      ? data.detail.map((e) => `${e.loc?.at(-1)}: ${e.msg}`).join('; ')
      : defaults[response.status] ||
        data?.detail ||
        'Не удалось выполнить запрос.';
    throw new ApiError(
      message,
      response.status,
      response.headers.get('X-Request-ID'),
    );
  }
  return response.status === 204 ? null : response.json();
}
export function mediaUrl(url) {
  if (!url) return undefined;
  return url;
}
export function time(seconds = 0) {
  const n = Math.max(0, Math.floor(seconds || 0));
  return `${Math.floor(n / 60)
    .toString()
    .padStart(2, '0')}:${(n % 60).toString().padStart(2, '0')}`;
}
export function duration(seconds) {
  if (seconds == null) return 'Длительность уточняется';
  const mins = Math.floor(seconds / 60);
  return mins >= 60
    ? `${Math.floor(mins / 60)} ч ${mins % 60} мин`
    : `${mins} мин`;
}
export const statuses = {
  pending: 'В очереди',
  downloading: 'Скачивание',
  extracting_audio: 'Извлечение аудио',
  transcribing: 'Расшифровка',
  indexing: 'Индексация',
  summarizing: 'Генерация конспекта',
  ready: 'Готово к просмотру',
  failed: 'Ошибка обработки',
};

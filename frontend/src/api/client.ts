const BASE = '/api/v1';

let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

const STATUS_MESSAGES: Record<number, string> = {
  401: 'Нужно войти в аккаунт',
  403: 'Недостаточно прав',
  404: 'Не найдено',
  409: 'Лекция ещё обрабатывается',
  413: 'Файл слишком большой',
  415: 'Этот формат не поддерживается',
  429: 'Слишком много попыток, подождите немного',
  503: 'AI-помощник сейчас недоступен',
};

export function setAccessToken(token: string | null) {
  accessToken = token;
}

/** Exchanges the HttpOnly refresh cookie for a new access token. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= fetch(`${BASE}/auth/refresh`, {
    method: 'POST',
    credentials: 'include',
  })
    .then(async (response) => {
      accessToken = response.ok ? (await response.json()).access_token : null;
      return response.ok;
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null;
    });

  return refreshing;
}

const CODE_MESSAGES: Record<string, string> = {
  media_unsupported_format: 'Этот формат не поддерживается. Подойдут MP4, WebM, MOV, MKV или аудиофайл',
  media_too_large: 'Файл слишком большой',
  media_unreadable: 'Файл повреждён или это не видео',
  media_no_audio: 'В файле нет звуковой дорожки — расшифровывать нечего',
  media_too_long: 'Запись слишком длинная: до 4 часов',
  url_unavailable: 'По ссылке не нашлось видео. Проверьте, что оно открыто для всех',
  url_live_stream: 'Прямые трансляции не поддерживаются — дождитесь записи',
  llm_unavailable: 'AI-помощник сейчас недоступен. Поиск и расшифровка работают',
};

export function messageForCode(code: string | null | undefined): string | undefined {
  return code ? CODE_MESSAGES[code] : undefined;
}

async function errorMessage(response: Response): Promise<string> {
  const data = await response.json().catch(() => null);
  const detail = data?.detail;
  const byCode = messageForCode(data?.code);

  if (byCode) return byCode;

  if (Array.isArray(detail)) {
    return detail.map((item: { msg: string }) => item.msg).join('; ');
  }

  // Domain errors carry an English detail meant for developers; users get a
  // Russian message for the status instead.
  return STATUS_MESSAGES[response.status] ?? 'Что-то пошло не так';
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
};

export async function api<T>(
  path: string,
  { method = 'GET', body, signal }: RequestOptions = {},
  retry = true,
): Promise<T> {
  const isForm = body instanceof FormData;
  let response: Response;

  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      signal,
      credentials: 'include',
      headers: {
        ...(body !== undefined && !isForm
          ? { 'Content-Type': 'application/json' }
          : {}),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: isForm
        ? body
        : body === undefined
          ? undefined
          : JSON.stringify(body),
    });
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error;
    throw new ApiError('Сервер недоступен', 0);
  }

  if (response.status === 401 && retry && !path.startsWith('/auth/')) {
    if (await refreshSession()) return api<T>(path, { method, body, signal }, false);
    window.dispatchEvent(new Event('lectio:signed-out'));
  }

  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }

  return (response.status === 204 ? null : await response.json()) as T;
}

/** Upload with progress: fetch cannot report upload progress. */
export function uploadWithProgress<T>(
  path: string,
  form: FormData,
  onProgress: (fraction: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.open('POST', `${BASE}${path}`);
    xhr.withCredentials = true;

    if (accessToken) xhr.setRequestHeader('Authorization', `Bearer ${accessToken}`);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
        return;
      }

      errorMessage(new Response(xhr.responseText, { status: xhr.status })).then(
        (message) => reject(new ApiError(message, xhr.status)),
      );
    };
    xhr.onerror = () => reject(new ApiError('Сервер недоступен', 0));
    xhr.send(form);
  });
}

export type StreamHandlers = Record<string, (data: unknown) => void>;

/** POST that answers with server-sent events; calls handlers by event name. */
export async function streamEvents(
  path: string,
  body: unknown,
  handlers: StreamHandlers,
  signal?: AbortSignal,
  retry = true,
): Promise<void> {
  let response: Response;

  try {
    response = await fetch(`${BASE}${path}`, {
      method: 'POST',
      signal,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify(body),
    });
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error;
    throw new ApiError('Сервер недоступен', 0);
  }

  if (response.status === 401 && retry && (await refreshSession())) {
    return streamEvents(path, body, handlers, signal, false);
  }

  if (!response.ok || !response.body) {
    throw new ApiError(await errorMessage(response), response.status);
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += value;
    let boundary: number;

    while ((boundary = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      let name = 'message';
      const data: string[] = [];

      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) name = line.slice(6).trim();
        else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
      }

      if (data.length) handlers[name]?.(JSON.parse(data.join('\n')));
    }
  }
}

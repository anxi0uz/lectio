import {
  Bookmark as BookmarkIcon,
  Captions,
  FileVideo,
  Maximize,
  Minimize,
  Pause,
  Play,
  RotateCcw,
  RotateCw,
  Volume2,
  VolumeX,
} from 'lucide-react';
import {
  type RefObject,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import type { Segment } from '../../api/types';
import { timecode } from '../../lib/format';

const SPEEDS = [0.75, 1, 1.25, 1.5, 1.75, 2];
const IDLE_MS = 2500;

/** Index of the segment playing at `time`, or -1. Segments are sorted. */
export function segmentAt(segments: Segment[], time: number): number {
  let low = 0;
  let high = segments.length - 1;
  let found = -1;

  while (low <= high) {
    const mid = (low + high) >> 1;

    if (segments[mid].start_seconds <= time) {
      found = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }

  return found;
}

export function Player({
  videoRef,
  src,
  title,
  duration,
  segments,
  chapterStarts,
  bookmarkMarks,
  time,
  onTime,
  onPlayingChange,
  onLoaded,
  onBookmark,
  placeholder,
}: {
  videoRef: RefObject<HTMLVideoElement | null>;
  src: string | null;
  title: string;
  duration: number | null;
  segments: Segment[];
  chapterStarts: number[];
  bookmarkMarks: number[];
  time: number;
  onTime: (seconds: number) => void;
  onPlayingChange: (playing: boolean) => void;
  onLoaded: () => void;
  onBookmark?: () => void;
  placeholder?: React.ReactNode;
}) {
  const container = useRef<HTMLDivElement>(null);
  const seekBar = useRef<HTMLDivElement>(null);
  const idleTimer = useRef<number>(undefined);

  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [captions, setCaptions] = useState(true);
  const [fullscreen, setFullscreen] = useState(false);
  const [idle, setIdle] = useState(false);
  const [hover, setHover] = useState<{ x: number; time: number } | null>(null);
  const [videoDuration, setVideoDuration] = useState(duration ?? 0);

  const total = videoDuration || duration || 0;
  const caption = useMemo(() => {
    const index = segmentAt(segments, time);
    const segment = segments[index];
    return segment && time <= segment.end_seconds + 0.5 ? segment.text : null;
  }, [segments, time]);

  const wake = useCallback(() => {
    setIdle(false);
    window.clearTimeout(idleTimer.current);
    idleTimer.current = window.setTimeout(() => setIdle(true), IDLE_MS);
  }, []);

  const toggle = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) void video.play();
    else video.pause();
  }, [videoRef]);

  const skip = useCallback(
    (delta: number) => {
      const video = videoRef.current;
      if (video) video.currentTime = Math.min(Math.max(video.currentTime + delta, 0), total);
    },
    [videoRef, total],
  );

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void container.current?.requestFullscreen();
  }, []);

  useEffect(() => {
    const onChange = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  // Keyboard shortcuts, ignored while typing in a field.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (target.closest('input, textarea, select, [contenteditable]')) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;

      const actions: Record<string, () => void> = {
        ' ': toggle,
        k: toggle,
        ArrowLeft: () => skip(-5),
        ArrowRight: () => skip(5),
        j: () => skip(-10),
        l: () => skip(10),
        f: toggleFullscreen,
        c: () => setCaptions((value) => !value),
        m: () => setMuted((value) => !value),
        b: () => onBookmark?.(),
      };
      const action = actions[event.key];

      if (action && src) {
        event.preventDefault();
        action();
        wake();
      }
    };

    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [toggle, skip, toggleFullscreen, onBookmark, src, wake]);

  useEffect(() => {
    if (videoRef.current) videoRef.current.muted = muted;
  }, [muted, videoRef]);

  useEffect(() => {
    if (videoRef.current) videoRef.current.playbackRate = speed;
  }, [speed, videoRef]);

  const positionAt = (clientX: number) => {
    const rect = seekBar.current!.getBoundingClientRect();
    const fraction = Math.min(Math.max((clientX - rect.left) / rect.width, 0), 1);
    return { x: clientX - rect.left, time: fraction * total };
  };

  const startSeek = (event: React.PointerEvent) => {
    const video = videoRef.current;
    if (!video || !total) return;

    (event.target as HTMLElement).setPointerCapture(event.pointerId);
    video.currentTime = positionAt(event.clientX).time;

    const move = (e: PointerEvent) => {
      video.currentTime = positionAt(e.clientX).time;
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
    };

    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  const pct = (seconds: number) => `${total ? (seconds / total) * 100 : 0}%`;

  if (!src) {
    return (
      <div className="player">
        <div className="player-placeholder">
          <FileVideo size={40} strokeWidth={1.4} />
          {placeholder}
        </div>
      </div>
    );
  }

  return (
    <div
      ref={container}
      className={`player${idle && playing ? ' idle' : ''}`}
      onMouseMove={wake}
      onMouseLeave={() => playing && setIdle(true)}
    >
      <video
        ref={videoRef}
        src={src}
        preload="metadata"
        playsInline
        onClick={toggle}
        onDoubleClick={toggleFullscreen}
        onLoadedMetadata={(e) => {
          setVideoDuration(e.currentTarget.duration);
          onLoaded();
        }}
        onTimeUpdate={(e) => onTime(e.currentTarget.currentTime)}
        onSeeked={(e) => onTime(e.currentTarget.currentTime)}
        onPlay={() => {
          setPlaying(true);
          onPlayingChange(true);
          wake();
        }}
        onPause={() => {
          setPlaying(false);
          setIdle(false);
          onPlayingChange(false);
        }}
      />

      <div className="player-top">
        <span>{title}</span>
        {onBookmark && (
          <button className="player-btn" onClick={onBookmark} title="Закладка на этом моменте (B)">
            <BookmarkIcon size={18} />
          </button>
        )}
      </div>

      {!playing && (
        <div className="player-center">
          <div className="player-big-play">
            <Play size={28} fill="white" />
          </div>
        </div>
      )}

      {captions && caption && <div className="player-caption">{caption}</div>}

      <div className="player-controls">
        <div
          ref={seekBar}
          className="seek"
          onPointerDown={startSeek}
          onPointerMove={(e) => total && setHover(positionAt(e.clientX))}
          onPointerLeave={() => setHover(null)}
        >
          <div className="seek-track">
            <div className="seek-fill" style={{ width: pct(time) }} />
            {chapterStarts.filter((s) => s > 0).map((start) => (
              <span key={start} className="seek-chapter" style={{ left: pct(start) }} />
            ))}
            {bookmarkMarks.map((mark) => (
              <span key={mark} className="seek-mark" style={{ left: pct(mark) }} />
            ))}
          </div>
          {hover && (
            <span className="seek-tooltip" style={{ left: hover.x }}>
              {timecode(hover.time)}
            </span>
          )}
        </div>

        <div className="player-row">
          <button className="player-btn" onClick={toggle} title={playing ? 'Пауза (K)' : 'Смотреть (K)'}>
            {playing ? <Pause size={20} fill="white" /> : <Play size={20} fill="white" />}
          </button>
          <button className="player-btn" onClick={() => skip(-10)} title="Назад 10 с (J)">
            <RotateCcw size={18} />
          </button>
          <button className="player-btn" onClick={() => skip(10)} title="Вперёд 10 с (L)">
            <RotateCw size={18} />
          </button>
          <button className="player-btn" onClick={() => setMuted(!muted)} title="Звук (M)">
            {muted ? <VolumeX size={18} /> : <Volume2 size={18} />}
          </button>
          <span className="player-time">
            {timecode(time)} / {timecode(total)}
          </span>

          <span style={{ flex: 1 }} />

          <button
            className="player-speed"
            onClick={() => setSpeed(SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length])}
            title="Скорость"
          >
            {speed}×
          </button>
          <button
            className={`player-btn${captions ? ' on' : ''}`}
            onClick={() => setCaptions(!captions)}
            title="Субтитры (C)"
          >
            <Captions size={18} />
          </button>
          <button className="player-btn" onClick={toggleFullscreen} title="Во весь экран (F)">
            {fullscreen ? <Minimize size={18} /> : <Maximize size={18} />}
          </button>
        </div>
      </div>
    </div>
  );
}

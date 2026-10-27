import {
  BookMarked,
  BookOpen,
  ClipboardCheck,
  Flag,
  Footprints,
  GraduationCap,
  Medal,
  MessageSquare,
  Search,
  Star,
  ThumbsUp,
  Trophy,
} from 'lucide-react';
import type { ReactNode } from 'react';

import type { Achievement, Level } from '../api/types';
import { plural } from '../lib/format';

const ICONS: Record<string, ReactNode> = {
  first_step: <Footprints size={20} />,
  finisher: <Flag size={20} />,
  marathon: <Medal size={20} />,
  quiz_first: <ClipboardCheck size={20} />,
  quiz_perfect: <Star size={20} />,
  quiz_master: <GraduationCap size={20} />,
  curious: <Search size={20} />,
  notes: <BookMarked size={20} />,
  voice: <MessageSquare size={20} />,
  enrolled: <BookOpen size={20} />,
  fan: <ThumbsUp size={20} />,
};

export function LevelBar({ level }: { level: Level }) {
  const span = level.next_level_xp - level.level_xp;
  const share = span ? (level.xp - level.level_xp) / span : 0;

  return (
    <div className="level">
      <div className="level-badge">
        <span className="label">Уровень</span>
        <span className="level-number">{level.level}</span>
      </div>
      <div className="level-body">
        <div className="level-row">
          <span className="level-xp">{level.xp} XP</span>
          <span className="muted">
            ещё {level.next_level_xp - level.xp} до уровня {level.level + 1}
          </span>
        </div>
        <div className="bar bar-brand">
          <div style={{ width: `${Math.round(Math.min(Math.max(share, 0), 1) * 100)}%` }} />
        </div>
      </div>
    </div>
  );
}

export function AchievementGrid({ achievements }: { achievements: Achievement[] }) {
  // Unlocked first, then those closest to done.
  const sorted = [...achievements].sort(
    (a, b) => Number(b.unlocked) - Number(a.unlocked) || b.progress / b.target - a.progress / a.target,
  );

  return (
    <div className="achievements">
      {sorted.map((achievement) => (
        <div key={achievement.id} className={`achievement${achievement.unlocked ? ' unlocked' : ''}`}>
          <span className="achievement-icon">{ICONS[achievement.id] ?? <Trophy size={20} />}</span>
          <div className="achievement-body">
            <div className="achievement-title">{achievement.title}</div>
            <div className="achievement-desc">{achievement.description}</div>
            {!achievement.unlocked && achievement.target > 1 && (
              <div className="achievement-progress">
                <div className="bar">
                  <div style={{ width: `${Math.round((achievement.progress / achievement.target) * 100)}%` }} />
                </div>
                <span className="mono">
                  {achievement.progress}/{achievement.target}
                </span>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export function achievementsCount(n: number) {
  return plural(n, 'достижение', 'достижения', 'достижений');
}

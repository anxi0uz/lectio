import { Trophy } from 'lucide-react';

import { useLeaderboard, useMyAchievements } from '../api/hooks';
import type { LeaderboardEntry } from '../api/types';
import { useAuth } from '../auth/AuthProvider';
import { AchievementGrid, LevelBar, achievementsCount } from '../components/Gamification';
import { Avatar, Empty, Skeleton } from '../components/ui';
import { fullName } from '../lib/format';

export function LeaderboardPage() {
  const { user } = useAuth();
  const mine = useMyAchievements();
  const board = useLeaderboard();
  const unlocked = mine.data?.achievements.filter((item) => item.unlocked).length ?? 0;
  const meInTop = board.data?.top.some((entry) => entry.user.id === user?.id);

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <div className="eyebrow">Геймификация</div>
          <h1>Рейтинг</h1>
          <p>Очки за просмотренные лекции, тесты и участие в обсуждениях. В рейтинге — студенты.</p>
        </div>
      </section>

      <section className="card card-pad" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {mine.data ? (
          <>
            <LevelBar level={mine.data.level} />
            <div>
              <h3 className="section-label">
                Достижения · {unlocked} из {mine.data.achievements.length}
              </h3>
              <AchievementGrid achievements={mine.data.achievements} />
            </div>
          </>
        ) : (
          <Skeleton height={220} />
        )}
      </section>

      <section className="card card-pad">
        <h3 className="section-label">Топ-10 студентов</h3>
        {board.isPending ? (
          <Skeleton height={240} />
        ) : board.data?.top.length ? (
          <div>
            {board.data.top.map((entry) => (
              <Row key={entry.user.id} entry={entry} me={entry.user.id === user?.id} />
            ))}
            {board.data.me && !meInTop && (
              <>
                <div className="leader-gap">⋯</div>
                <Row entry={board.data.me} me />
              </>
            )}
          </div>
        ) : (
          <Empty icon={<Trophy size={22} />} title="Рейтинг пока пуст">
            Посмотрите лекцию или пройдите тест — и окажетесь первым.
          </Empty>
        )}
      </section>
    </div>
  );
}

function Row({ entry, me }: { entry: LeaderboardEntry; me: boolean }) {
  return (
    <div className={`leader${me ? ' me' : ''}`}>
      <span className="leader-rank">{String(entry.rank).padStart(2, '0')}</span>
      <Avatar user={entry.user} size={40} />
      <div className="leader-name">
        <b>
          {fullName(entry.user)}
          {me && <span className="accent"> · вы</span>}
        </b>
        <span className="muted">
          Уровень {entry.level.level} · {achievementsCount(entry.achievements)}
        </span>
      </div>
      <span className="leader-xp">
        {entry.level.xp}
        <span className="muted"> XP</span>
      </span>
    </div>
  );
}

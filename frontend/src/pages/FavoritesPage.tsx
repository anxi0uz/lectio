import { Heart } from 'lucide-react';
import { Link } from 'react-router';

import { useFavorites } from '../api/hooks';
import { LectureCard } from '../components/LectureCard';
import { Empty, Skeleton } from '../components/ui';

export function FavoritesPage() {
  const { data: favorites, isLoading } = useFavorites();

  return (
    <div className="page">
      <section className="card page-header">
        <div>
          <div className="eyebrow">Моё</div>
          <h1>Избранное</h1>
          <p>Лекции, к которым хочется вернуться.</p>
        </div>
      </section>
      <section className="card card-pad">
        {isLoading ? (
          <div className="grid">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} height={240} />
            ))}
          </div>
        ) : favorites?.length ? (
          <div className="grid">
            {favorites.map((lecture) => (
              <LectureCard key={lecture.id} lecture={lecture} />
            ))}
          </div>
        ) : (
          <Empty
            icon={<Heart size={22} />}
            title="Пока пусто"
            action={
              <Link to="/lectures" className="btn btn-sm">
                К лекциям
              </Link>
            }
          >
            Нажмите на сердечко на странице лекции, чтобы добавить её сюда.
          </Empty>
        )}
      </section>
    </div>
  );
}

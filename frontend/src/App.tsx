import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Compass } from 'lucide-react';
import type { ReactNode } from 'react';
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from 'react-router';

import { ApiError } from './api/client';
import { AuthProvider, useAuth } from './auth/AuthProvider';
import { Layout } from './components/Layout';
import { Empty, Spinner, ToastProvider } from './components/ui';
import { AuthPage } from './pages/AuthPage';
import { BookmarksPage } from './pages/BookmarksPage';
import { CoursePage } from './pages/CoursePage';
import { CoursesPage } from './pages/CoursesPage';
import { FavoritesPage } from './pages/FavoritesPage';
import { HomePage } from './pages/HomePage';
import { LecturePage } from './pages/lecture/LecturePage';
import { LecturesPage } from './pages/LecturesPage';
import { ProfilePage } from './pages/ProfilePage';
import { SearchPage } from './pages/SearchPage';
import { UploadPage } from './pages/UploadPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      // Client errors will not fix themselves on retry.
      retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
    },
  },
});

function RequireAuth({ children, teacher }: { children: ReactNode; teacher?: boolean }) {
  const { user, ready, isTeacher } = useAuth();
  const location = useLocation();

  if (!ready) {
    return (
      <div className="empty">
        <Spinner />
      </div>
    );
  }

  if (!user) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  }

  if (teacher && !isTeacher) return <Navigate to="/" replace />;

  return children;
}

function NotFound() {
  return (
    <div className="card">
      <Empty
        icon={<Compass size={22} />}
        title="Страница не найдена"
        action={
          <Link to="/" className="btn btn-sm">
            На главную
          </Link>
        }
      />
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<AuthPage mode="login" />} />
              <Route path="/register" element={<AuthPage mode="register" />} />
              <Route element={<Layout />}>
                <Route index element={<HomePage />} />
                <Route path="lectures" element={<LecturesPage />} />
                <Route path="lectures/:id" element={<LecturePage />} />
                <Route path="courses" element={<CoursesPage />} />
                <Route path="courses/:id" element={<CoursePage />} />
                <Route path="search" element={<SearchPage />} />
                <Route path="favorites" element={<RequireAuth><FavoritesPage /></RequireAuth>} />
                <Route path="bookmarks" element={<RequireAuth><BookmarksPage /></RequireAuth>} />
                <Route path="profile" element={<RequireAuth><ProfilePage /></RequireAuth>} />
                <Route path="upload" element={<RequireAuth teacher><UploadPage /></RequireAuth>} />
                <Route path="*" element={<NotFound />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}

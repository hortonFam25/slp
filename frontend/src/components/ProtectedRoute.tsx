import { PropsWithChildren } from 'react';
import { useIsAuthenticated } from '@azure/msal-react';
import { Navigate, useLocation } from 'react-router-dom';

export function ProtectedRoute({ children }: PropsWithChildren) {
  const isAuthed = useIsAuthenticated();
  const location = useLocation();
  
  if (!isAuthed) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return <>{children}</>;
}



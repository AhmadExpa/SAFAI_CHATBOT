import { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';

interface ProtectedRouteProps {
    children: ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
    const { isAuthenticated, isLoading } = useAuth();

    if (isLoading) {
        // Show loading state while checking authentication
        return (
            <div className="min-h-screen flex items-center justify-center bg-gradient-main">
                <div className="text-center">
                    <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center mb-4 border-2 border-primary/30 mx-auto animate-pulse">
                        <span className="text-primary font-bold text-2xl">⬡</span>
                    </div>
                    <p className="text-muted-foreground">Loading...</p>
                </div>
            </div>
        );
    }

    if (!isAuthenticated) {
        // Check if user has registered before
        const hasRegistered = localStorage.getItem('saifai-registered');
        // Redirect to login if registered, signup if not
        return <Navigate to={hasRegistered ? '/login' : '/signup'} replace />;
    }

    return <>{children}</>;
}

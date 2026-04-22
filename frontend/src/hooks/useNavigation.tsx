import { useNavigate } from 'react-router-dom';

// Route constants for consistency
export const ROUTES = {
    HOME: '/',
    LOGIN: '/login',
    SIGNUP: '/signup',
    LIBRARY: '/library',
    EXPLORE: '/explore',
    CODEX: '/codex',
    CHAT: '/chat',
} as const;

/**
 * Custom hook providing centralized navigation utilities
 * Wraps useNavigate from react-router-dom with typed navigation functions
 */
export function useNavigation() {
    const navigate = useNavigate();

    return {
        // Direct navigation functions
        navigateToHome: () => navigate(ROUTES.HOME),
        navigateToLogin: () => navigate(ROUTES.LOGIN),
        navigateToSignup: () => navigate(ROUTES.SIGNUP),
        navigateToLibrary: () => navigate(ROUTES.LIBRARY),
        navigateToExplore: () => navigate(ROUTES.EXPLORE),
        navigateToCodex: () => navigate(ROUTES.CODEX),
        navigateToChat: () => navigate(ROUTES.CHAT),

        // Generic navigation with route constant
        navigateTo: (route: string) => navigate(route),

        // Navigation with state
        navigateWithState: (route: string, state: unknown) => navigate(route, { state }),

        // Go back
        goBack: () => navigate(-1),

        // Route constants for external use
        routes: ROUTES,
    };
}

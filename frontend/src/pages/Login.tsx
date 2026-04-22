import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { Mail, Lock } from "lucide-react";
import { ThemeToggler } from "../components/global/themeToggler";
import { useAuth } from "../contexts/AuthContext";
import { getGoogleOAuthUrl } from "../lib/api";
import topContainer from "../assets/1.png";
import bgTheme from "../assets/8.png";
import companyLogo from "../assets/2.png";
import googleLogo from "../assets/google_logo.png";
import appleLogo from "../assets/apple_logo.png";

const Login = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isLoading, error: authError } = useAuth();

  // Get the page user was trying to access before being redirected to login
  const from =
    (location.state as { from?: { pathname: string } })?.from?.pathname || "/";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    // Validation
    if (!email.trim()) {
      setError("Please enter your email");
      return;
    }
    if (!password) {
      setError("Please enter your password");
      return;
    }

    try {
      await login(email, password);
      // Navigate to the page user was trying to access, or home
      navigate(from, { replace: true });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Login failed";
      setError(errorMessage);
    }
  };

  const displayError = error || authError;

  return (
    <div className="pb-5 w-full flex flex-col items-center justify-center relative font-sans gradient-bg overflow-hidden">
      <div className="absolute top-80 dark:top-0 flex items-center justify-center w-full inset-0 z-0">
        <img
          src={bgTheme}
          alt="Background"
          className="dark:w-[70%] w-[80%] mx-auto object-stretch dark:invert opacity-50 dark:opacity-20"
        />
      </div>
      {/* Theme Toggler */}
      <div className="absolute top-4 right-4 z-50">
        <ThemeToggler />
      </div>

      {/* Top Visual */}
      <div className="relative w-full max-w-4xl flex flex-col items-center z-10">
        <img
          src={topContainer}
          alt="Network Illustration"
          className="w-[420px] md:w-[570px] object-contain "
        />

        {/* Logo moved UP */}
        <img
          src={companyLogo}
          alt="Logo"
          className="w-16 h-16 md:w-20 md:h-20 object-contain drop-shadow-2xl rounded-full -mt-28"
        />
      </div>

      {/* Main Content */}

      {/* Wrapper */}
      <div
        className="
       w-[95%] 
sm:w-[90%]
md:w-[70%]
lg:w-[60%]
            bg-gradient-to-t
            from-white/90
            via-white/70
            dark:from-black/90
            dark:via-gray-800/70
            to-transparent
            rounded-2xl
            px-4
sm:px-8
md:px-20
lg:px-40
            py-6
            overflow-hidden 
            z-20
            "
      >
        <div className="w-full flex flex-col items-center mt-5">
          <h1 className="text-4xl md:text-5xl font-serif text-gray-900 dark:text-white tracking-wide text-center">
            WELCOME
          </h1>
          <p className="text-gray-500 dark:text-white text-sm tracking-wide mb-4 text-center">
            Enter Your Credentials
          </p>
          <div className="w-full max-w-xl mx-auto space-y-4">
            {/* Error Message */}
            {displayError && (
              <div className="bg-red-100 dark:bg-red-900/20 border border-red-400 dark:border-red-700 text-red-700 dark:text-red-400 px-4 py-2 rounded text-sm">
                {displayError}
              </div>
            )}

            {/* Email */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center">
                <Mail className="h-6 w-6 text-gray-500 dark:text-gray-400" />
              </div>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@email.com"
                disabled={isLoading}
                className="w-full h-12 pl-12 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800/80 focus:ring-2 focus:ring-cyan-400 disabled:opacity-50"
              />
            </div>

            {/* Password */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center">
                <Lock className="h-6 w-6 text-gray-500 dark:text-gray-400" />
              </div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••"
                disabled={isLoading}
                className="w-full h-12 pl-12 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800/80 tracking-wider focus:ring-2 focus:ring-cyan-400 disabled:opacity-50"
              />
            </div>

            {/* Forgot Password */}
            <div className="flex justify-end relative bottom-2">
              <Link
                to="/forgot-password"
                className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
              >
                Forgot Password?
              </Link>
            </div>

            {/* Button */}
            <button
              onClick={handleLogin}
              disabled={isLoading}
              className="w-full h-11 bg-cyan-400 hover:bg-cyan-500 disabled:bg-cyan-300 text-white font-semibold shadow-md transition disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {isLoading ? "Logging in..." : "Login"}
            </button>

            {/* Divider */}
            <div className="flex items-center py-2">
              <div className="flex-1 border-t border-gray-300 dark:border-gray-600" />
              <span className="mx-3 text-sm text-gray-600 dark:text-gray-300">
                OR
              </span>
              <div className="flex-1 border-t border-gray-300 dark:border-gray-600" />
            </div>

            {/* Social */}
            <div className="flex justify-center space-x-4">
              <button
                onClick={() => (window.location.href = getGoogleOAuthUrl())}
                className="w-16 h-12 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md flex items-center justify-center p-2 hover:bg-gray-50 dark:hover:bg-gray-600"
              >
                <img
                  src={googleLogo}
                  alt="Google"
                  className="w-full h-full object-contain"
                />
              </button>
              <button className="w-16 h-12 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md flex items-center justify-center p-2 hover:bg-gray-50 dark:hover:bg-gray-600">
                <img
                  src={appleLogo}
                  alt="Apple"
                  className="w-full h-full object-contain"
                />
              </button>
            </div>

            {/* Sign Up Link */}
            <p className="text-center text-sm text-gray-500 dark:text-gray-400">
              Don't have an account?{" "}
              <Link
                to="/signup"
                className="text-blue-400 font-medium hover:text-blue-500"
              >
                Register Now
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;

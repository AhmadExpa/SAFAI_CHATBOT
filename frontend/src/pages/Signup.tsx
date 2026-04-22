import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { User, Mail, Lock, AlertCircle, Loader } from "lucide-react";
import { ThemeToggler } from "../components/global/themeToggler";
import { useTheme } from "../hooks/useTheme";
import { useAuth } from "../contexts/AuthContext";
import { getGoogleOAuthUrl } from "../lib/api";
import topContainer from "../assets/1.png";
import bgTheme from "../assets/8.png";
import companyLogo from "../assets/2.png";
import googleLogo from "../assets/google_logo.png";
import appleLogo from "../assets/apple_logo.png";

const Signup = () => {
  const { theme } = useTheme();
  const navigate = useNavigate();
  const { signup, isLoading, error: authError } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [localError, setLocalError] = useState("");

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError("");

    // Validation
    if (!fullName.trim()) {
      setLocalError("Please enter your full name");
      return;
    }

    if (!email.trim()) {
      setLocalError("Please enter your email");
      return;
    }

    if (!password) {
      setLocalError("Please enter a password");
      return;
    }

    if (password !== confirmPassword) {
      setLocalError("Passwords do not match");
      return;
    }

    if (password.length < 6) {
      setLocalError("Password must be at least 6 characters");
      return;
    }

    try {
      await signup(fullName, email, password);
      navigate("/chat");
    } catch (err) {
      // Error is already set by the context
      setLocalError(authError || "Signup failed. Please try again.");
    }
  };

  const displayError = localError || authError;

  return (
    <div className=" pb-5 w-full flex flex-col items-center justify-center relative font-sans gradient-bg overflow-hidden">
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
          className="w-[420px] md:w-[570px] object-contain"
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
        <div className="w-full flex flex-col items-center mt-5 ">
          <h1 className="text-4xl md:text-5xl font-serif text-gray-900 dark:text-blue-500 tracking-wide text-center">
            WELCOME
          </h1>
          <p className="text-gray-500 dark:text-blue-500 text-sm tracking-wide mb-4 text-center">
            Register Your Data
          </p>

          <div className="w-full max-w-xl mx-auto space-y-4">
            {/* Error Message */}
            {displayError && (
              <div className="flex items-center gap-2 p-3 bg-red-100 dark:bg-red-900/30 border border-red-300 dark:border-red-700 rounded-md">
                <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0" />
                <p className="text-sm text-red-600 dark:text-red-400">
                  {displayError}
                </p>
              </div>
            )}

            {/* Name */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center">
                <User className="h-6 w-6 text-gray-500 dark:text-gray-400" />
              </div>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Your Name"
                disabled={isLoading}
                className="w-full h-12 pl-12 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800/80 focus:ring-2 focus:ring-cyan-400 disabled:opacity-50"
              />
            </div>

            {/* Email */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center">
                <Mail className="h-6 w-6 text-gray-500 dark:text-gray-400" />
              </div>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="yourid@server.com"
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

            {/* Confirm Password */}
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center">
                <Lock className="h-6 w-6 text-gray-500 dark:text-gray-400" />
              </div>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••••"
                disabled={isLoading}
                className="w-full h-12 pl-12 border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800/80 tracking-wider focus:ring-2 focus:ring-cyan-400 disabled:opacity-50"
              />
            </div>

            {/* Button */}
            <button
              onClick={handleSignup}
              disabled={isLoading}
              className="w-full h-11 bg-cyan-400 hover:bg-cyan-500 disabled:bg-gray-400 text-white font-semibold shadow-md transition flex items-center justify-center gap-2"
            >
              {isLoading && <Loader className="h-4 w-4 animate-spin" />}
              {isLoading ? "Signing Up..." : "Sign Up"}
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
                onClick={() => window.location.href = getGoogleOAuthUrl()}
                className="w-16 h-12 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md flex items-center justify-center p-2 hover:bg-gray-50 dark:hover:bg-gray-600"
              >
                <img
                  src={googleLogo}
                  alt="Google"
                  className="w-full h-full object-contain"
                />
              </button>
              <button className="w-16 h-12 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 rounded-md flex items-center justify-center p-2">
                <img
                  src={appleLogo}
                  alt="Apple"
                  className="w-full h-full object-contain"
                />
              </button>
            </div>

            {/* Login */}
            <p className="text-center text-sm text-gray-500 dark:text-gray-400">
              Already signed up?{" "}
              <Link to="/login" className="text-blue-400 font-medium">
                Login Now
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Signup;

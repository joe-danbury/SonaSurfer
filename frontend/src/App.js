import { useState, useEffect } from 'react';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [accessToken, setAccessToken] = useState(null);

  // Check for tokens on mount and handle OAuth callback
  useEffect(() => {
    // Check if we have stored tokens
    const storedToken = localStorage.getItem('spotify_access_token');
    const storedExpiresAt = localStorage.getItem('spotify_expires_at');
    
    if (storedToken && storedExpiresAt) {
      const expiresAt = parseInt(storedExpiresAt);
      const now = Math.floor(Date.now() / 1000);
      
      if (now < expiresAt) {
        // Token is still valid
        setAccessToken(storedToken);
        setIsAuthenticated(true);
      } else {
        // Token expired, try to refresh
        const refreshToken = localStorage.getItem('spotify_refresh_token');
        if (refreshToken) {
          refreshAccessToken(refreshToken);
        } else {
          // No refresh token, clear storage
          clearTokens();
        }
      }
    }
    
    // Handle OAuth callback from URL hash
    const hash = window.location.hash;
    if (hash) {
      const params = new URLSearchParams(hash.substring(1));
      const token = params.get('access_token');
      const refreshToken = params.get('refresh_token');
      const expiresAt = params.get('expires_at');
      
      if (token && refreshToken && expiresAt) {
        // Store tokens
        localStorage.setItem('spotify_access_token', token);
        localStorage.setItem('spotify_refresh_token', refreshToken);
        localStorage.setItem('spotify_expires_at', expiresAt);
        
        setAccessToken(token);
        setIsAuthenticated(true);
        
        // Clear URL hash
        window.history.replaceState(null, null, ' ');
      }
      
      // Check for errors
      const error = params.get('error');
      if (error) {
        const errorMessage = params.get('message') || 'Authentication failed';
        setMessages([{
          text: `Login failed: ${errorMessage}`,
          sender: 'system'
        }]);
        // Clear URL
        window.history.replaceState(null, null, ' ');
      }
    }
  }, []);

  const handleLogin = () => {
    window.location.href = `${API_BASE_URL}/auth/spotify`;
  };

  const handleLogout = () => {
    clearTokens();
    setAccessToken(null);
    setIsAuthenticated(false);
    setMessages([]);
  };

  const clearTokens = () => {
    localStorage.removeItem('spotify_access_token');
    localStorage.removeItem('spotify_refresh_token');
    localStorage.removeItem('spotify_expires_at');
  };

  const refreshAccessToken = async (refreshToken) => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh?refresh_token=${refreshToken}`, {
        method: 'POST',
      });
      
      if (response.ok) {
        const data = await response.json();
        localStorage.setItem('spotify_access_token', data.access_token);
        localStorage.setItem('spotify_refresh_token', data.refresh_token);
        localStorage.setItem('spotify_expires_at', data.expires_at.toString());
        setAccessToken(data.access_token);
        setIsAuthenticated(true);
      } else {
        // Refresh failed, clear tokens
        clearTokens();
        setIsAuthenticated(false);
      }
    } catch (error) {
      console.error('Failed to refresh token:', error);
      clearTokens();
      setIsAuthenticated(false);
    }
  };

  const handleSendMessage = (e) => {
    e.preventDefault();
    if (inputValue.trim()) {
      setMessages([...messages, { text: inputValue, sender: 'user' }]);
      setInputValue('');
    }
  };

  return (
    <div className="min-h-screen bg-[#4a9b8e] flex">
      {/* Left half - Chat Window */}
      <div className="w-1/2 flex flex-col h-screen">
        {/* Login Header */}
        <div className="border-b border-white/20 p-4 flex justify-between items-center">
          <h1 className="text-xl font-bold text-white">SonaSurfer 🎵</h1>
          {isAuthenticated ? (
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-white/20 text-white rounded-lg hover:bg-white/30 transition-colors text-sm"
            >
              Logout
            </button>
          ) : (
            <button
              onClick={handleLogin}
              className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors font-semibold text-sm"
            >
              Login with Spotify
            </button>
          )}
        </div>

        {/* Message History Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {!isAuthenticated ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <p className="text-white/70 text-lg mb-4">
                  Please login with Spotify to start building playlists
                </p>
                <button
                  onClick={handleLogin}
                  className="px-6 py-3 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors font-semibold"
                >
                  Login with Spotify
                </button>
              </div>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-white/70 text-lg">
                Start a conversation to build your playlist...
              </p>
            </div>
          ) : (
            messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${message.sender === 'user' ? 'justify-end' : message.sender === 'system' ? 'justify-center' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 ${
                    message.sender === 'user'
                      ? 'bg-white text-gray-800'
                      : message.sender === 'system'
                      ? 'bg-red-500/20 text-red-100 border border-red-500/30'
                      : 'bg-white/20 text-white'
                  }`}
                >
                  <p>{message.text}</p>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Chat Input Box */}
        <div className="border-t border-white/20 p-4">
          <form onSubmit={handleSendMessage} className="flex gap-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={isAuthenticated ? "Ask me to create a playlist..." : "Please login first..."}
              disabled={!isAuthenticated}
              className="flex-1 px-4 py-3 rounded-lg bg-white/90 text-gray-800 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              disabled={!isAuthenticated}
              className="px-6 py-3 bg-white text-[#4a9b8e] rounded-lg font-semibold hover:bg-white/90 transition-colors focus:outline-none focus:ring-2 focus:ring-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </form>
        </div>
      </div>

      {/* Right half - Playlist Display */}
      <div className="w-1/2 bg-white flex flex-col h-screen overflow-y-auto">
        <div className="p-8 flex gap-8">
          {/* Left side - Cover and Tracklist */}
          <div className="flex-shrink-0 flex flex-col">
            {/* Playlist Cover */}
            <div className="mb-6 flex justify-center">
              <div className="w-64 h-64 bg-gray-200 rounded-lg shadow-lg flex items-center justify-center">
                <svg
                  className="w-24 h-24 text-gray-400"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z"
                    clipRule="evenodd"
                  />
                </svg>
              </div>
            </div>

            {/* Tracklist */}
            <div className="space-y-2">
              <h3 className="text-lg font-semibold text-gray-700 mb-4">Tracks</h3>
              <div className="space-y-1">
                {/* Placeholder tracks - will be replaced with actual data */}
                <div className="flex items-center gap-3 p-3 rounded hover:bg-gray-100 transition-colors">
                  <div className="w-10 h-10 bg-gray-300 rounded flex-shrink-0"></div>
                  <div className="flex-1 min-w-0">
                    <p className="text-gray-400 text-sm">Track name will appear here</p>
                    <p className="text-gray-500 text-xs">Artist name</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right side - Playlist Name and Description */}
          <div className="flex-1 flex flex-col">
            {/* Playlist Name */}
            <div className="mb-4">
              <h2 className="text-3xl font-bold text-gray-800">
                My Playlist
              </h2>
            </div>

            {/* Description */}
            <div className="mb-6">
              <p className="text-gray-500 text-sm">
                Playlist description will appear here...
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
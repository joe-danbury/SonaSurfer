import { useState, useEffect } from 'react';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [accessToken, setAccessToken] = useState(null);
  const [showPlaylistForm, setShowPlaylistForm] = useState(false);
  const [playlist, setPlaylist] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    public: true
  });
  const [isCreating, setIsCreating] = useState(false);
  const [isLoadingResponse, setIsLoadingResponse] = useState(false);

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

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoadingResponse) {
      return;
    }

    const userMessage = inputValue.trim();
    setInputValue('');
    
    // Add user message to chat
    const newMessages = [...messages, { text: userMessage, sender: 'user' }];
    setMessages(newMessages);
    setIsLoadingResponse(true);

    // Convert messages to API format (include conversation history)
    const apiMessages = newMessages
      .filter(msg => msg.sender === 'user' || msg.sender === 'assistant')
      .map(msg => ({
        role: msg.sender === 'user' ? 'user' : 'assistant',
        content: msg.text
      }));

    // Build request URL with playlist_id if available
    // TODO: Move playlist_id management to backend later
    let chatUrl = `${API_BASE_URL}/chat`;
    if (playlist?.id) {
      chatUrl += `?playlist_id=${playlist.id}`;
    }

    // Build headers
    const headers = {
      'Content-Type': 'application/json',
    };
    if (accessToken && playlist?.id) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    // Add placeholder assistant message that we'll update incrementally
    // Use a unique ID to track this specific response (declared outside try-catch for error handling)
    const responseId = Date.now() + Math.random();
    const initialMessages = [...newMessages, { text: '', sender: 'assistant', responseId }];
    setMessages(initialMessages);

    try {
        // Call Claude API with streaming
        const response = await fetch(chatUrl, {
          method: 'POST',
          headers: headers,
          body: JSON.stringify({
            messages: apiMessages
          })
        });

      if (response.ok) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let accumulatedText = '';
        let streamComplete = false;

        while (!streamComplete) {
          const { done, value } = await reader.read();
          
          if (done) {
            break;
          }

          // Decode chunk and add to buffer
          buffer += decoder.decode(value, { stream: true });
          
          // Process complete SSE messages (separated by \n\n)
          while (buffer.includes('\n\n')) {
            const messageEnd = buffer.indexOf('\n\n');
            const message = buffer.substring(0, messageEnd);
            buffer = buffer.substring(messageEnd + 2);
            
            if (message.startsWith('data: ')) {
              try {
                const data = JSON.parse(message.slice(6)); // Remove 'data: ' prefix
                
                if (data.type === 'chunk') {
                  accumulatedText += data.content;
                  // Update the assistant message incrementally by finding it via responseId
                  setMessages(prev => {
                    const updated = [...prev];
                    const messageIndex = updated.findIndex(msg => msg.responseId === responseId);
                    if (messageIndex !== -1) {
                      updated[messageIndex] = { ...updated[messageIndex], text: accumulatedText };
                    } else {
                      // Fallback: if message not found, append new one (shouldn't happen)
                      updated.push({ text: accumulatedText, sender: 'assistant', responseId });
                    }
                    return updated;
                  });
                } else if (data.type === 'error') {
                  setMessages(prev => {
                    const updated = [...prev];
                    const messageIndex = updated.findIndex(msg => msg.responseId === responseId);
                    if (messageIndex !== -1) {
                      updated[messageIndex] = { text: `Error: ${data.content}`, sender: 'system', responseId };
                    } else {
                      updated.push({ text: `Error: ${data.content}`, sender: 'system', responseId });
                    }
                    return updated;
                  });
                  setIsLoadingResponse(false);
                  return;
                } else if (data.type === 'done') {
                  // Stream complete
                  streamComplete = true;
                  break;
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', e, message);
              }
            }
          }
        }
        
        // Refresh playlist if tracks were added
        // TODO: Move playlist refresh to backend/WebSocket for real-time updates
        if (playlist?.id && accessToken) {
          try {
            const playlistResponse = await fetch(`${API_BASE_URL}/playlists/${playlist.id}`, {
              headers: {
                'Authorization': `Bearer ${accessToken}`
              }
            });
            if (playlistResponse.ok) {
              const playlistData = await playlistResponse.json();
              setPlaylist(playlistData);
            }
          } catch (error) {
            console.error('Failed to refresh playlist:', error);
          }
        }
      } else {
        const errorData = await response.json();
        setMessages(prev => {
          const updated = [...prev];
          const messageIndex = updated.findIndex(msg => msg.responseId === responseId);
          if (messageIndex !== -1) {
            updated[messageIndex] = {
              text: `Error: ${errorData.detail || 'Failed to get response from Claude'}`,
              sender: 'system',
              responseId
            };
          } else {
            updated.push({
              text: `Error: ${errorData.detail || 'Failed to get response from Claude'}`,
              sender: 'system',
              responseId
            });
          }
          return updated;
        });
      }
    } catch (error) {
      // If we have a responseId, update that message, otherwise add new error message
      setMessages(prev => {
        const updated = [...prev];
        const messageIndex = updated.findIndex(msg => msg.responseId === responseId);
        if (messageIndex !== -1) {
          updated[messageIndex] = {
            text: `Error: ${error.message}`,
            sender: 'system',
            responseId
          };
        } else {
          updated.push({
            text: `Error: ${error.message}`,
            sender: 'system'
          });
        }
        return updated;
      });
    } finally {
      setIsLoadingResponse(false);
    }
  };

  const handleCreatePlaylist = () => {
    setShowPlaylistForm(true);
  };

  const handleCloseForm = () => {
    setShowPlaylistForm(false);
    setFormData({ name: '', description: '', public: true });
  };

  const handleFormChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleFormSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      return;
    }

    setIsCreating(true);
    try {
      const response = await fetch(`${API_BASE_URL}/playlists`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({
          name: formData.name,
          description: formData.description || null,
          public: formData.public
        })
      });

      if (response.ok) {
        const playlistData = await response.json();
        setPlaylist(playlistData);
        setShowPlaylistForm(false);
        setFormData({ name: '', description: '', public: true });
      } else {
        const errorData = await response.json();
        setMessages([...messages, {
          text: `Failed to create playlist: ${errorData.detail || 'Unknown error'}`,
          sender: 'system'
        }]);
      }
    } catch (error) {
      setMessages([...messages, {
        text: `Error creating playlist: ${error.message}`,
        sender: 'system'
      }]);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-green-500 flex relative">
      {/* Top Right - Login/Logout Button */}
      <div className="absolute top-4 right-4 z-10">
        {isAuthenticated ? (
          <button
            onClick={handleLogout}
            className="px-4 py-2 bg-white/20 text-white rounded-lg hover:bg-white/30 transition-colors text-sm backdrop-blur-sm"
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

      {/* Left half - Chat Window */}
      <div className={`w-1/2 flex flex-col h-screen ${showPlaylistForm ? 'blur-sm pointer-events-none' : ''}`}>
        {/* Header */}
        <div className="border-b border-white/20 p-4">
          <h1 className="text-xl font-bold text-white">SonaSurfer 🎵</h1>
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
              <div className="text-center">
                <p className="text-white/70 text-lg mb-4">
                  Start a conversation to build your playlist...
                </p>
                {!playlist && (
                  <button
                    onClick={handleCreatePlaylist}
                    className="px-6 py-3 bg-white text-green-500 rounded-lg hover:bg-white/90 transition-colors font-semibold"
                  >
                    Create Playlist
                  </button>
                )}
              </div>
            </div>
          ) : (
            <>
              {messages.map((message, index) => (
                <div
                  key={message.responseId || `msg-${index}-${message.sender}`}
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
                    <p className="whitespace-pre-wrap">{message.text}</p>
                  </div>
                </div>
              ))}
              {isLoadingResponse && (
                <div className="flex justify-start">
                  <div className="bg-white/20 text-white rounded-lg px-4 py-2">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 bg-white rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-white rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-white rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                  </div>
                </div>
              )}
            </>
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
              disabled={!isAuthenticated || isLoadingResponse}
              autoComplete="off"
              className="flex-1 px-4 py-3 rounded-lg bg-white/90 text-gray-800 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              disabled={!isAuthenticated || isLoadingResponse || !inputValue.trim()}
              className="px-6 py-3 bg-white text-green-500 rounded-lg font-semibold hover:bg-white/90 transition-colors focus:outline-none focus:ring-2 focus:ring-white/50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoadingResponse ? 'Sending...' : 'Send'}
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
              {playlist?.images?.[0]?.url ? (
                <img 
                  src={playlist.images[0].url} 
                  alt={playlist.name}
                  className="w-64 h-64 rounded-lg shadow-lg object-cover"
                />
              ) : (
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
              )}
            </div>

            {/* Tracklist */}
            <div className="space-y-2">
              <h3 className="text-lg font-semibold text-gray-700 mb-4">Tracks</h3>
              <div className="space-y-1">
                {playlist?.tracks?.items && playlist.tracks.items.length > 0 ? (
                  playlist.tracks.items.map((item, index) => (
                    <div key={index} className="flex items-center gap-3 p-3 rounded hover:bg-gray-100 transition-colors">
                      {item.track?.album?.images?.[2]?.url ? (
                        <img 
                          src={item.track.album.images[2].url} 
                          alt={item.track.name}
                          className="w-10 h-10 rounded flex-shrink-0"
                        />
                      ) : (
                        <div className="w-10 h-10 bg-gray-300 rounded flex-shrink-0"></div>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-gray-800 text-sm font-medium">{item.track.name}</p>
                        <p className="text-gray-500 text-xs">{item.track.artists.map(a => a.name).join(', ')}</p>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="flex items-center gap-3 p-3 rounded hover:bg-gray-100 transition-colors">
                    <div className="w-10 h-10 bg-gray-300 rounded flex-shrink-0"></div>
                    <div className="flex-1 min-w-0">
                      <p className="text-gray-400 text-sm">No tracks yet</p>
                      <p className="text-gray-500 text-xs">Tracks will appear here</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right side - Playlist Name and Description */}
          <div className="flex-1 flex flex-col">
            {/* Playlist Name */}
            <div className="mb-4">
              <h2 className="text-3xl font-bold text-gray-800">
                {playlist?.name || 'My Playlist'}
              </h2>
            </div>

            {/* Description */}
            <div className="mb-6">
              <p className="text-gray-500 text-sm">
                {playlist?.description || 'Playlist description will appear here...'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Playlist Creation Form Modal */}
      {showPlaylistForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-8 w-full max-w-md mx-4">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold text-gray-800">Create New Playlist</h2>
              <button
                onClick={handleCloseForm}
                className="text-gray-500 hover:text-gray-700 text-2xl font-bold"
                disabled={isCreating}
              >
                ×
              </button>
            </div>
            
            <form onSubmit={handleFormSubmit} className="space-y-4" autoComplete="off">
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-2">
                  Playlist Name *
                </label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  value={formData.name}
                  onChange={handleFormChange}
                  required
                  disabled={isCreating}
                  autoComplete="off"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
                  placeholder="My Awesome Playlist"
                />
              </div>

              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-2">
                  Description
                </label>
                <textarea
                  id="description"
                  name="description"
                  value={formData.description}
                  onChange={handleFormChange}
                  disabled={isCreating}
                  rows={3}
                  autoComplete="off"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50"
                  placeholder="Describe your playlist..."
                />
              </div>

              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="public"
                  name="public"
                  checked={formData.public}
                  onChange={handleFormChange}
                  disabled={isCreating}
                  className="w-4 h-4 text-green-500 border-gray-300 rounded focus:ring-green-500 disabled:opacity-50"
                />
                <label htmlFor="public" className="ml-2 text-sm text-gray-700">
                  Make playlist public
                </label>
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={handleCloseForm}
                  disabled={isCreating}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isCreating || !formData.name.trim()}
                  className="flex-1 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-semibold"
                >
                  {isCreating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
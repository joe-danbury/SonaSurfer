import { useState } from 'react';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');

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
        {/* Message History Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-white/70 text-lg">
                Start a conversation to build your playlist...
              </p>
            </div>
          ) : (
            messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${message.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 ${
                    message.sender === 'user'
                      ? 'bg-white text-gray-800'
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
              placeholder="Ask me to create a playlist..."
              className="flex-1 px-4 py-3 rounded-lg bg-white/90 text-gray-800 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-white/50"
            />
            <button
              type="submit"
              className="px-6 py-3 bg-white text-[#4a9b8e] rounded-lg font-semibold hover:bg-white/90 transition-colors focus:outline-none focus:ring-2 focus:ring-white/50"
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
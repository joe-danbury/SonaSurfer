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

      {/* Right half - Reserved for future use */}
      <div className="w-1/2 bg-white/10"></div>
    </div>
  );
}

export default App;
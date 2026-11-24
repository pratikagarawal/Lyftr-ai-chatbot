
import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function createSessionId() {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function App() {
  // Create a fresh session whenever the page loads
  const [sessionId, setSessionId] = useState(() => createSessionId())

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const bottomRef = useRef(null)

  // Load conversation history for the current session
  useEffect(() => {
    const controller = new AbortController()

    async function loadMessages() {
      setMessages([])
      setError('')

      try {
        const response = await fetch(
          `${API_URL}/sessions/${encodeURIComponent(sessionId)}/messages`,
          { signal: controller.signal }
        )

        if (response.status === 404) {
          return
        }

        if (!response.ok) {
          throw new Error('Unable to load conversation')
        }

        const data = await response.json()
        setMessages(data.messages || [])
      } catch (err) {
        if (err.name !== 'AbortError') {
          console.error('History loading failed:', err)
        }
      }
    }

    loadMessages()

    return () => controller.abort()
  }, [sessionId])

  // Automatically scroll to the latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: 'smooth'
    })
  }, [messages, loading])

  // Send message
  async function sendMessage(e) {
    e.preventDefault()

    const text = input.trim()

    if (!text || loading) return

    setError('')
    setInput('')

    setMessages(prev => [
      ...prev,
      { role: 'user', content: text }
    ])

    setLoading(true)

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: text
        })
      })

      const data = await response.json()

      if (!response.ok) {
        if (response.status === 422) {
          throw new Error(
            data.detail || 'Invalid message. Please check your input.'
          )
        }

        if (response.status === 503) {
          throw new Error(
            'AI service is temporarily unavailable. Please try again later.'
          )
        }

        throw new Error(data.detail || 'Something went wrong.')
      }

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: data.reply,
          metadata: data.metadata
        }
      ])

    } catch (err) {
      setError(err.message || 'Unable to connect to the server')
    } finally {
      setLoading(false)
    }
  }

  // Start a new conversation
  function newChat() {
    if (loading) return

    setSessionId(createSessionId())
    setMessages([])
    setInput('')
    setError('')
  }

  return (
    <div className="app">

      <aside className="sidebar">

        <div className="brand">
          <span className="brand-icon">✦</span>
          <span>Lyftr AI</span>
        </div>

        <button
          className="new-chat"
          onClick={newChat}
          disabled={loading}
        >
          + New Chat
        </button>

        <div className="sidebar-label">
          CHAT HISTORY
        </div>

        <div className="session-list">
          <div className="empty-sessions">
            Your current conversation is active.
          </div>
        </div>

        <div className="sidebar-bottom">
          <span>Powered by Gemini</span>
          <span>Lyftr AI Chatbot v1.0</span>
        </div>

      </aside>

      <main className="chat-area">

        <header className="topbar">

          <div>
            <h2>AI Assistant</h2>

            <span className="online-status">
              <span className="status-dot"></span>
              Ready to help
            </span>
          </div>

          <button
            className="header-button"
            onClick={newChat}
            disabled={loading}
          >
            New conversation
          </button>

        </header>

        <section className="messages">

          {messages.length === 0 && !loading && (
            <div className="welcome">

              <div className="welcome-icon">✦</div>

              <h1>Hello! I'm Lyftr AI.</h1>

              <p>
                Your intelligent assistant. Ask me anything,
                explore ideas, or get help with your work.
              </p>

            </div>
          )}

          {messages.map((message, index) => (
            <div
              key={`${sessionId}-${index}`}
              data-testid={
                message.role === 'assistant'
                  ? 'assistant-message'
                  : undefined
              }
              className={`message-row ${
                message.role === 'user' ? 'user-row' : 'ai-row'
              }`}
            >

              {message.role !== 'user' && (
                <div className="avatar">✦</div>
              )}

              <div
                className={`message ${
                  message.role === 'user' ? 'user-message' : 'ai-message'
                }`}
              >

                <div className="message-content">
                  {message.role === 'assistant' ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {message.content}
                    </ReactMarkdown>
                  ) : (
                    message.content
                  )}
                </div>

                {message.role === 'assistant' && (
                  <div className="response-metadata">

                    <span data-testid="meta-source">
                      Source: {message.metadata?.resolution_source || 'N/A'}
                    </span>

                    <span data-testid="meta-model">
                      Model: {message.metadata?.model || 'N/A'}
                    </span>

                    <span data-testid="meta-latency">
                      Latency: {message.metadata?.latency_ms ?? 'N/A'} ms
                    </span>

                    <span data-testid="meta-input-tokens">
                      Input tokens: {message.metadata?.input_tokens ?? 0}
                    </span>

                    <span data-testid="meta-output-tokens">
                      Output tokens: {message.metadata?.output_tokens ?? 0}
                    </span>

                    <span>
                      {message.metadata?.model_fallback_used
                        ? 'Model fallback used'
                        : 'No model fallback'}
                    </span>

                  </div>
                )}

              </div>

              {message.role === 'user' && (
                <div className="avatar user-avatar">You</div>
              )}

            </div>
          ))}

          {loading && (
            <div className="message-row ai-row">

              <div className="avatar">✦</div>

              <div className="message ai-message typing">
                Lyftr AI is thinking...
                <span className="dots">•••</span>
              </div>

            </div>
          )}

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <div ref={bottomRef}></div>

        </section>

        <footer className="input-area">

          <form onSubmit={sendMessage} className="chat-form">

            <textarea
              data-testid="chat-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  sendMessage(e)
                }
              }}
              placeholder="Message Lyftr AI..."
              rows="1"
              disabled={loading}
            />

            <button
              data-testid="send-button"
              type="submit"
              className="send-button"
              disabled={!input.trim() || loading}
            >
              {loading ? '...' : '↑'}
            </button>

          </form>

          <p className="disclaimer">
            Lyftr AI can make mistakes. Verify important information.
          </p>

        </footer>

      </main>

    </div>
  )
}

export default App

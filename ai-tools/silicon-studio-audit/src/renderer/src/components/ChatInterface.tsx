import { useState, useEffect, useRef } from 'react'
import { apiClient } from '../api/client'

interface Message {
    role: 'user' | 'assistant'
    content: string
}

interface Model {
    id: string
    name: string
}

const CHAT_STORAGE_KEY = 'silicon-studio-chat-history';

export function ChatInterface() {
    const [messages, setMessages] = useState<Message[]>(() => {
        // Load from localStorage on initial mount
        try {
            const saved = localStorage.getItem(CHAT_STORAGE_KEY);
            return saved ? JSON.parse(saved) : [];
        } catch {
            return [];
        }
    })
    const [input, setInput] = useState('')
    const [models, setModels] = useState<Model[]>([])
    const [selectedModel, setSelectedModel] = useState<string>('')
    const [loading, setLoading] = useState(false)
    const messagesEndRef = useRef<HTMLDivElement>(null)

    // Save messages to localStorage whenever they change
    useEffect(() => {
        localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
    }, [messages]);

    useEffect(() => {
        // Fetch available models
        apiClient.engine.getModels().then((data: any[]) => {
            const downloaded = data.filter(m => m.downloaded);
            setModels(downloaded)
            if (downloaded.length > 0) setSelectedModel(downloaded[0].id)
        }).catch(console.error)
    }, [])

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    const handleClearChat = () => {
        setMessages([]);
        localStorage.removeItem(CHAT_STORAGE_KEY);
    };

    const handleSend = async () => {
        if (!input.trim() || !selectedModel) return

        const userMsg: Message = { role: 'user', content: input }
        setMessages(prev => [...prev, userMsg])
        setInput('')
        setLoading(true)

        try {
            const response = await apiClient.engine.chat(selectedModel, [...messages, userMsg])
            const assistantMsg: Message = { role: 'assistant', content: response.content }
            setMessages(prev => [...prev, assistantMsg])
        } catch (err) {
            console.error(err)
            setMessages(prev => [...prev, { role: 'assistant', content: "Error: Failed to generate response." }])
        } finally {
            setLoading(false)
        }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    return (
        <div className="h-full flex flex-col space-y-4">
            <div className="flex justify-between items-center bg-black/20 p-3 rounded-lg border border-white/5">
                <h2 className="text-xl font-bold text-white">Chat</h2>
                <div className="flex items-center gap-3">
                    {messages.length > 0 && (
                        <button
                            onClick={handleClearChat}
                            className="text-xs text-gray-400 hover:text-red-400 transition-colors px-2 py-1 rounded hover:bg-white/5"
                            title="Clear chat history"
                        >
                            Clear
                        </button>
                    )}
                    <select
                        value={selectedModel}
                        onChange={(e) => setSelectedModel(e.target.value)}
                        className="bg-black/40 text-gray-300 text-sm rounded px-2 py-1 border border-white/10 outline-none focus:border-blue-500"
                    >
                        {models.map(m => (
                            <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                    </select>
                </div>
            </div>

            <div className="flex-1 bg-black/10 rounded-xl border border-white/5 p-4 overflow-y-auto space-y-4">
                {messages.length === 0 && (
                    <div className="h-full flex flex-col items-center justify-center text-gray-600 opacity-50">
                        <span className="text-4xl mb-2">💬</span>
                        <p>Select a model and start chatting</p>
                    </div>
                )}
                {messages.map((msg, i) => (
                    <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div
                            className={`max-w-[80%] px-4 py-2 rounded-2xl text-sm leading-relaxed ${msg.role === 'user'
                                ? 'bg-blue-600 text-white rounded-br-none'
                                : 'bg-white/10 text-gray-200 rounded-bl-none'
                                }`}
                        >
                            {msg.content}
                        </div>
                    </div>
                ))}
                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-white/10 px-4 py-2 rounded-2xl rounded-bl-none flex space-x-1 items-center">
                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                            <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                        </div>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            <div className="bg-black/20 p-2 rounded-lg border border-white/10 flex items-center space-x-2">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Type a message..."
                    className="flex-1 bg-transparent text-white px-3 py-2 outline-none placeholder-gray-600"
                />
                <button
                    onClick={handleSend}
                    disabled={!input.trim() || loading}
                    className={`p-2 rounded-full transition-colors ${input.trim() && !loading ? 'bg-blue-600 text-white hover:bg-blue-500' : 'bg-gray-800 text-gray-500 cursor-not-allowed'
                        }`}
                >
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5 transform rotate-90">
                        <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                    </svg>
                </button>
            </div>
        </div>
    )
}

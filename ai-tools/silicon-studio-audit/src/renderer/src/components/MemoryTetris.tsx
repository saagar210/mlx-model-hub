import { useState, useEffect } from 'react'
import { apiClient, type SystemStats } from '../api/client'

export function MemoryTetris() {
    const [stats, setStats] = useState<SystemStats | null>(null)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const data = await apiClient.monitor.getStats()
                setStats(data)
                setError(null)
            } catch (err: any) {
                setError("Failed to connect to monitoring service")
            }
        }

        fetchStats()
        const interval = setInterval(fetchStats, 1000)
        return () => clearInterval(interval)
    }, [])

    if (error) {
        return (
            <div className="h-full flex items-center justify-center text-red-400">
                {error}
            </div>
        )
    }

    if (!stats) {
        return (
            <div className="h-full flex items-center justify-center text-gray-500 animate-pulse">
                Connecting to System Monitor...
            </div>
        )
    }

    const formatBytes = (bytes: number) => {
        const gb = bytes / (1024 * 1024 * 1024)
        return `${gb.toFixed(1)} GB`
    }

    return (
        <div className="flex flex-col space-y-6">


            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* RAM Block */}
                <div className="bg-black/20 p-6 rounded-xl border border-white/10">
                    <div className="flex justify-between items-end mb-2">
                        <span className="text-sm font-bold text-gray-400 uppercase">Unified Memory</span>
                        <span className="text-2xl font-mono text-white">{stats.memory.percent}%</span>
                    </div>
                    <div className="h-32 bg-gray-800 rounded-lg overflow-hidden flex flex-col-reverse relative">
                        {/* Visualizing "Tetris" blocks */}
                        <div
                            className="w-full bg-gradient-to-t from-blue-600 to-cyan-400 transition-all duration-500 ease-in-out"
                            style={{ height: `${stats.memory.percent}%` }}
                        />
                        {/* Grid overlay */}
                        <div className="absolute inset-0 grid grid-cols-8 grid-rows-4 gap-0.5 opacity-20 pointer-events-none">
                            {Array.from({ length: 32 }).map((_, i) => (
                                <div key={i} className="border border-black"></div>
                            ))}
                        </div>
                    </div>
                    <div className="flex justify-between text-xs text-gray-500 mt-2 font-mono">
                        <span>Used: {formatBytes(stats.memory.used)}</span>
                        <span>Total: {formatBytes(stats.memory.total)}</span>
                    </div>
                </div>

                {/* CPU Block */}
                <div className="bg-black/20 p-6 rounded-xl border border-white/10">
                    <div className="flex justify-between items-end mb-2">
                        <span className="text-sm font-bold text-gray-400 uppercase">CPU Load</span>
                        <span className="text-2xl font-mono text-white">{stats.cpu.percent}%</span>
                    </div>
                    <div className="h-32 flex items-end space-x-1">
                        {/* Making a fake history chart or just current bar per core could be cool, keeping it simple for now */}
                        <div className="w-full h-full bg-gray-800 rounded-lg overflow-hidden relative">
                            <div
                                className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-purple-600 to-pink-400 transition-all duration-300"
                                style={{ height: `${stats.cpu.percent}%` }}
                            />
                        </div>
                    </div>
                    <div className="flex justify-between text-xs text-gray-500 mt-2 font-mono">
                        <span>Cores: {stats.cpu.cores}</span>
                        <span>System: macOS (Apple Silicon)</span>
                    </div>
                </div>
            </div>

            {/* Disk Info (Quick Bar) */}
            <div className="bg-black/20 p-4 rounded-xl border border-white/10">
                <div className="flex justify-between items-center mb-1">
                    <span className="text-xs font-bold text-gray-500 uppercase">Local Storage</span>
                    <span className="text-xs text-gray-400">{stats.disk.percent.toFixed(1)}% Used</span>
                </div>
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-yellow-500 transition-all duration-1000"
                        style={{ width: `${stats.disk.percent}%` }}
                    />
                </div>
            </div>
        </div>
    )
}

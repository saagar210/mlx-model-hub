import { useState, useEffect } from 'react'
import { apiClient, type SystemStats } from '../api/client'

export function MemoryTetrisMini() {
    const [stats, setStats] = useState<SystemStats | null>(null)

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const data = await apiClient.monitor.getStats()
                setStats(data)
            } catch (err) {
                // Silent fail for mini widget
            }
        }
        fetchStats()
        const interval = setInterval(fetchStats, 2000) // Slower poll
        return () => clearInterval(interval)
    }, [])

    if (!stats) return null

    const formatBytes = (bytes: number) => {
        const gb = bytes / (1024 * 1024 * 1024)
        return `${Math.round(gb)}GB`
    }

    return (
        <div className="px-2 py-4">
            <div className="flex justify-between items-baseline mb-2">
                <div className="text-xs text-gray-500 uppercase font-semibold">Memory</div>
                <div className="text-[10px] text-green-400">{stats.memory.percent}%</div>
            </div>
            <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                    className="h-full bg-gradient-to-r from-green-500 to-emerald-400 transition-all duration-1000"
                    style={{ width: `${stats.memory.percent}%` }}
                />
            </div>
            <div className="flex justify-between text-[10px] text-gray-400 mt-1 font-mono">
                <span>{formatBytes(stats.memory.used)}</span>
                <span>{formatBytes(stats.memory.total)}</span>
            </div>
        </div>
    )
}

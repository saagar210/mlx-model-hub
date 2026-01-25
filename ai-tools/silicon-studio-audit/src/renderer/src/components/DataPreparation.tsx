import { useState } from 'react'
import { apiClient, type PreviewRow } from '../api/client'

export function DataPreparation() {
    const [filePath, setFilePath] = useState<string>("")
    const [fileName, setFileName] = useState<string>("")
    const [preview, setPreview] = useState<PreviewRow[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const [columns, setColumns] = useState<string[]>([])

    // Config State
    const [instructionCol, setInstructionCol] = useState("")
    const [inputCol, setInputCol] = useState("")
    const [outputCol, setOutputCol] = useState("")
    const [stripPii, setStripPii] = useState(false)
    const [modelFamily, setModelFamily] = useState("Llama")

    // Output Path State
    const [outputPath, setOutputPath] = useState("")

    const handleFileSelect = async () => {
        try {
            const path = await (window as any).electronAPI.selectFile();
            if (path) {
                setFilePath(path);
                // Extract filename from path (basic check for various OS separators)
                const name = path.split(/[/\\]/).pop() || path;
                setFileName(name);

                // Set default output path
                const defaultOut = path.replace(/\.csv$/i, '_train.jsonl');
                setOutputPath(defaultOut);

                setLoading(true);
                setError(null);

                const res = await apiClient.preparation.previewCsv(path);
                setPreview(res.data);

                if (res.data.length > 0) {
                    const cols = Object.keys(res.data[0]);
                    setColumns(cols);
                    // Auto-guess columns
                    setInstructionCol(cols.find(c => c.toLowerCase().includes('instruct') || c.toLowerCase().includes('prompt')) || cols[0] || "");
                    setInputCol(cols.find(c => c.toLowerCase().includes('input') || c.toLowerCase().includes('context')) || "");
                    setOutputCol(cols.find(c => c.toLowerCase().includes('output') || c.toLowerCase().includes('response') || c.toLowerCase().includes('answer')) || cols[cols.length - 1] || "");
                }
            }
        } catch (err: any) {
            setError("Failed to load file: " + err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleConvert = async () => {
        if (!filePath || !outputPath || !instructionCol || !outputCol) return
        setLoading(true)
        try {
            await apiClient.preparation.convertCsv(
                filePath,
                outputPath,
                instructionCol,
                inputCol || undefined,
                outputCol,
                stripPii,
                modelFamily
            )

            alert(`Success! Training data saved to: ${outputPath}`)
            // Reset state
            setPreview([])
            setFilePath("")
            setFileName("")
        } catch (err: any) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="h-full flex flex-col space-y-4">
            {/* Header / Title */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                        Data Preparation
                        <span className="text-xs px-2 py-1 bg-blue-500/20 text-blue-300 rounded border border-blue-500/20">BETA</span>
                    </h2>
                    <p className="text-gray-400 text-sm mt-1">Convert any data into fine-tuning data for LLMs</p>
                </div>
            </div>

            {/* ERROR DISPLAY */}
            {error && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 flex items-center justify-between">
                    <p className="text-red-400 text-sm">{error}</p>
                    <button onClick={() => setError(null)} className="text-red-400 hover:text-white">✕</button>
                </div>
            )}

            {/* CONFIGURATION TOOLBAR (ALWAYS VISIBLE) */}
            <div className="bg-black/20 border border-white/10 rounded-xl p-4 grid grid-cols-1 md:grid-cols-2 gap-6">

                {/* 1. Input File */}
                <div className="flex flex-col space-y-1">
                    <label className="text-xs font-bold text-gray-500 uppercase">Input Dataset (CSV)</label>
                    <button
                        onClick={handleFileSelect}
                        className={`flex items-center justify-between px-3 py-2 rounded-lg border text-sm transition-all text-left ${fileName
                            ? 'bg-blue-500/10 border-blue-500/30 text-blue-200'
                            : 'bg-white/5 border-white/10 text-gray-400 hover:bg-white/10'
                            }`}
                    >
                        <span className="truncate">{fileName || "Select File..."}</span>
                        <span className="opacity-50">📂</span>
                    </button>
                </div>

                {/* 2. Output Folder */}
                <div className="flex flex-col space-y-1">
                    <label className="text-xs font-bold text-gray-500 uppercase">Output Path</label>
                    <button
                        onClick={async () => {
                            const path = await (window as any).electronAPI.selectDirectory();
                            if (path) setOutputPath(path + "/" + (fileName ? fileName.replace('.csv', '_train.jsonl') : 'train.jsonl'));
                        }}
                        className={`flex items-center justify-between px-3 py-2 rounded-lg border text-sm transition-all text-left ${outputPath
                            ? 'bg-green-500/10 border-green-500/30 text-green-200'
                            : 'bg-white/5 border-white/10 text-gray-400 hover:bg-white/10'
                            }`}
                        title={outputPath}
                    >
                        <span className="truncate">{outputPath ? "..." + outputPath.slice(-25) : "Select Folder..."}</span>
                        <span className="opacity-50">💾</span>
                    </button>
                </div>

                {/* 3. Model Family */}
                <div className="flex flex-col space-y-1">
                    <label className="text-xs font-bold text-gray-500 uppercase">Model Format</label>
                    <select
                        value={modelFamily}
                        onChange={(e) => setModelFamily(e.target.value)}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm outline-none focus:border-blue-500"
                    >
                        <option value="Llama">Llama (3, 3.1, 4)</option>
                        <option value="Mistral">Mistral / Mixtral</option>
                        <option value="Qwen">Qwen (2.5, 2.5-Coder)</option>
                        <option value="Gemma">Gemma (2, 3)</option>
                        <option value="Phi">Phi (3, 3.5, 4)</option>
                    </select>
                </div>

                {/* 4. PII Toggle */}
                <div className="flex flex-col space-y-1 justify-center">
                    <label className="text-xs font-bold text-gray-500 uppercase mb-1">Options</label>
                    <div className="flex items-center space-x-3">
                        <div
                            className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg border cursor-pointer transition-all ${stripPii ? 'bg-indigo-500/20 border-indigo-500/50 text-indigo-200' : 'bg-white/5 border-white/10 text-gray-400 hover:bg-white/10'
                                }`}
                            onClick={() => setStripPii(!stripPii)}
                        >
                            <div className={`w-4 h-4 rounded border flex items-center justify-center ${stripPii ? 'bg-indigo-500 border-indigo-500' : 'border-gray-500'}`}>
                                {stripPii && <span className="text-[10px] text-white">✓</span>}
                            </div>
                            <span className="text-xs font-medium">Auto-Remove PII</span>
                        </div>
                    </div>
                </div>
            </div>

            {/* PREVIEW & MAPPING AREA (Visible when file selected) */}
            {preview.length > 0 ? (
                <div className="flex-1 flex flex-col gap-4 overflow-hidden">

                    {/* Column Mapping Bar */}
                    <div className="bg-black/20 border border-white/10 rounded-xl p-3 flex flex-wrap items-center gap-4">
                        <span className="text-xs font-bold text-gray-500 uppercase mr-2">Map Columns:</span>

                        <div className="flex items-center gap-2">
                            <span className="text-xs text-blue-300">Instruction:</span>
                            <select
                                value={instructionCol}
                                onChange={(e) => setInstructionCol(e.target.value)}
                                className="bg-black/40 border border-white/10 rounded px-2 py-1 text-xs text-white outline-none focus:border-blue-500"
                            >
                                {columns.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                        </div>

                        <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-400">Input (Opt):</span>
                            <select
                                value={inputCol}
                                onChange={(e) => setInputCol(e.target.value)}
                                className="bg-black/40 border border-white/10 rounded px-2 py-1 text-xs text-white outline-none focus:border-blue-500"
                            >
                                <option value="">(None)</option>
                                {columns.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                        </div>

                        <div className="flex items-center gap-2">
                            <span className="text-xs text-green-300">Output:</span>
                            <select
                                value={outputCol}
                                onChange={(e) => setOutputCol(e.target.value)}
                                className="bg-black/40 border border-white/10 rounded px-2 py-1 text-xs text-white outline-none focus:border-blue-500"
                            >
                                {columns.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                        </div>

                        <div className="flex-1"></div>

                        <button
                            onClick={handleConvert}
                            disabled={loading || !outputPath}
                            className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-1.5 px-4 rounded-lg shadow-lg shadow-blue-500/20 transition-all text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        >
                            {loading ? 'Processing...' : 'Generate JSONL'}
                            {!loading && <span>✨</span>}
                        </button>
                    </div>

                    {/* Table */}
                    <div className="flex-1 overflow-auto rounded-xl border border-white/10 bg-black/20">
                        <table className="w-full text-left text-sm text-gray-400">
                            <thead className="bg-black/40 text-gray-500 uppercase font-bold text-[10px] tracking-wider sticky top-0">
                                <tr>
                                    {columns.map(header => (
                                        <th key={header} className={`px-6 py-3 whitespace-nowrap ${header === instructionCol ? 'text-blue-400' :
                                            header === outputCol ? 'text-green-400' :
                                                header === inputCol ? 'text-gray-300' : ''
                                            }`}>
                                            {header}
                                            {header === instructionCol && " (Instr)"}
                                            {header === outputCol && " (Out)"}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {preview.map((row, idx) => (
                                    <tr key={idx} className="hover:bg-white/5 transition-colors">
                                        {Object.values(row).map((cell, cIdx) => (
                                            <td key={cIdx} className="px-6 py-4 truncate max-w-[300px] border-r border-white/5 last:border-0">
                                                {cell}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            ) : (
                // EMPTY STATE
                <div className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-white/5 rounded-xl bg-white/[0.02]">
                    <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mb-4">
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
                        </svg>
                    </div>
                    <p className="text-gray-500 font-medium">Select a CSV dataset to begin</p>
                    <p className="text-gray-600 text-sm mt-2 max-w-sm text-center">
                        Configure your settings above, map your columns, and generate a clean JSONL file for training.
                    </p>
                </div>
            )}
        </div>
    )
}

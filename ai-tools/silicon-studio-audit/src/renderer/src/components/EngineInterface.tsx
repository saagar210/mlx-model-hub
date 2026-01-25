import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'

export function EngineInterface() {
    const [models, setModels] = useState<any[]>([])
    const [selectedModel, setSelectedModel] = useState('')
    const [datasetPath, setDatasetPath] = useState('train.jsonl')
    const [epochs, setEpochs] = useState(3)
    const [learningRate, setLearningRate] = useState(1e-4)
    // Advanced Params
    const [batchSize, setBatchSize] = useState(1)
    const [loraRank, setLoraRank] = useState(8)
    const [loraAlpha, setLoraAlpha] = useState(16)
    const [maxSeqLength, setMaxSeqLength] = useState(512)
    const [loraDropout, setLoraDropout] = useState(0.0)
    const [loraLayers, setLoraLayers] = useState(8)

    const [jobName, setJobName] = useState('')

    // ... (in startTraining body) ...

    body: JSON.stringify({
        model_id: selectedModel,
        dataset_path: datasetPath,
        epochs,
        learning_rate: learningRate,
        batch_size: batchSize,
        lora_rank: loraRank,
        lora_alpha: loraAlpha,
        max_seq_length: maxSeqLength,
        lora_dropout: loraDropout,
        lora_layers: loraLayers,
        job_name: jobName
    })

    const [jobStatus, setJobStatus] = useState<any>(null)
    const [loading, setLoading] = useState(false)

    useEffect(() => {
        apiClient.engine.getModels().then((data: any[]) => {
            const downloaded = data.filter(m => m.downloaded && !m.is_finetuned);
            setModels(downloaded)
            if (downloaded.length) setSelectedModel(downloaded[0].id)
        }).catch(console.error)
    }, [])

    const startTraining = async () => {
        if (!jobName.trim()) {
            alert("Please enter a Job Name to identify your fine-tuned model.")
            return
        }

        setLoading(true)
        try {
            // In a real app, we'd have a job ID returned and poll for it.
            // For MVP we just wait for the simulated response which might be quick.
            // Or we use the job_id to poll.
            const res = await fetch('http://127.0.0.1:8000/api/engine/finetune', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_id: selectedModel,
                    dataset_path: datasetPath,
                    epochs,
                    learning_rate: learningRate,
                    batch_size: batchSize,
                    lora_rank: loraRank,
                    lora_alpha: loraAlpha,
                    max_seq_length: maxSeqLength,
                    lora_dropout: loraDropout,
                    lora_layers: loraLayers,
                    job_name: jobName
                })
            })
            const data = await res.json()
            setJobStatus(data)
            pollStatus(data.job_id)
        } catch (err) {
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    const pollStatus = (jobId: string) => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`http://127.0.0.1:8000/api/engine/jobs/${jobId}`)
                const data = await res.json()
                setJobStatus(data)
                if (data.status === 'completed' || data.status === 'failed') {
                    clearInterval(interval)
                }
            } catch (e) {
                clearInterval(interval)
            }
        }, 1000)
    }

    return (
        <div className="bg-black/20 p-6 rounded-xl border border-white/10 space-y-6">
            <h3 className="text-xl font-bold text-white">Fine-Tuning Job Configuration</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                    <label className="text-xs uppercase text-gray-500 font-semibold">Job Name (Optional)</label>
                    <input
                        type="text"
                        placeholder="My Custom Model"
                        value={jobName}
                        onChange={e => setJobName(e.target.value)}
                        className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white outline-none focus:border-blue-500 placeholder-gray-600"
                    />
                </div>

                <div className="space-y-2">
                    <label className="text-xs uppercase text-gray-500 font-semibold">Base Model</label>
                    <select
                        className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white outline-none focus:border-blue-500"
                        value={selectedModel}
                        onChange={e => setSelectedModel(e.target.value)}
                    >
                        {models.map(m => <option key={m.id} value={m.id}>{m.name} ({m.size})</option>)}
                    </select>
                </div>

                <div className="space-y-2">
                    <label className="text-xs uppercase text-gray-500 font-semibold">Dataset Path</label>
                    <div className="flex space-x-2">
                        <input
                            type="text"
                            value={datasetPath}
                            readOnly
                            className="flex-1 bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white outline-none focus:border-blue-500 cursor-not-allowed opacity-70"
                        />
                        <button
                            onClick={async () => {
                                const path = await (window as any).electronAPI.selectFile();
                                if (path) setDatasetPath(path);
                            }}
                            className="bg-white/10 hover:bg-white/20 text-white px-4 py-2 rounded-lg transition-colors"
                        >
                            📂
                        </button>
                    </div>
                </div>

                <div className="space-y-2">
                    <label className="text-xs uppercase text-gray-500 font-semibold">Epochs</label>
                    <input
                        type="number"
                        value={epochs}
                        onChange={e => setEpochs(parseInt(e.target.value))}
                        className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white outline-none focus:border-blue-500"
                    />
                </div>

                <div className="space-y-2">
                    <label className="text-xs uppercase text-gray-500 font-semibold">Learning Rate</label>
                    <input
                        type="number"
                        step="0.0001"
                        min="0"
                        value={learningRate}
                        onChange={e => {
                            const val = parseFloat(e.target.value);
                            if (!isNaN(val)) setLearningRate(val);
                            else if (e.target.value === "") setLearningRate(0); // Handle empty
                        }}
                        className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white outline-none focus:border-blue-500"
                    />
                </div>

                {/* Advanced Parameters */}
                <div className="space-y-2">
                    <label className="text-xs uppercase text-gray-500 font-semibold">Batch Size</label>
                    <input
                        type="number"
                        value={batchSize}
                        onChange={e => setBatchSize(parseInt(e.target.value))}
                        className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white outline-none focus:border-blue-500"
                    />
                </div>

                <div className="space-y-2">
                    <label className="text-xs uppercase text-gray-500 font-semibold">LoRA Rank</label>
                    <input
                        type="number"
                        value={loraRank}
                        onChange={e => setLoraRank(parseInt(e.target.value))}
                        className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white outline-none focus:border-blue-500"
                    />
                </div>

                <div className="space-y-2">
                    <label className="text-xs uppercase text-gray-500 font-semibold">LoRA Alpha</label>
                    <input
                        type="number"
                        value={loraAlpha}
                        onChange={e => setLoraAlpha(parseInt(e.target.value))}
                        className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white outline-none focus:border-blue-500"
                    />
                </div>

                <div className="space-y-2">
                    <label className="text-xs uppercase text-gray-500 font-semibold">Max Sequence Length</label>
                    <input
                        type="number"
                        value={maxSeqLength}
                        onChange={e => setMaxSeqLength(parseInt(e.target.value))}
                        className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white outline-none focus:border-blue-500"
                    />
                </div>

                <div className="space-y-2">
                    <label className="text-xs uppercase text-gray-500 font-semibold">LoRA Dropout</label>
                    <input
                        type="number"
                        step="0.05"
                        min="0"
                        max="1"
                        value={loraDropout}
                        onChange={e => setLoraDropout(parseFloat(e.target.value))}
                        className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white outline-none focus:border-blue-500"
                    />
                </div>

                <div className="space-y-2">
                    <label className="text-xs uppercase text-gray-500 font-semibold">LoRA Layers (Last N)</label>
                    <input
                        type="number"
                        min="1"
                        max="100"
                        value={loraLayers}
                        onChange={e => setLoraLayers(parseInt(e.target.value))}
                        className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 text-white outline-none focus:border-blue-500"
                    />
                    <p className="text-[10px] text-gray-500">Number of layers to fine-tune (from end).</p>
                </div>
            </div>

            <div className="pt-4">
                {jobStatus ? (
                    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                        <div className="flex justify-between items-center mb-2">
                            <div className="flex flex-col">
                                <span className="font-bold text-white text-lg">
                                    {jobStatus.job_name || 'Fine-Tuning Job'}
                                </span>
                                <span className="font-mono text-xs text-gray-500">ID: {jobStatus.job_id || 'N/A'}</span>
                            </div>
                            <span className={`px-2 py-0.5 rounded text-xs uppercase font-bold ${jobStatus.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                                jobStatus.status === 'training' ? 'bg-blue-500/20 text-blue-400 animate-pulse' :
                                    jobStatus.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                                        'bg-gray-500/20 text-gray-400'
                                }`}>
                                {jobStatus.status}
                            </span>
                        </div>
                        {jobStatus.status === 'training' && (
                            <div className="w-full bg-gray-700 h-1.5 rounded-full overflow-hidden mt-2">
                                <div
                                    className="h-full bg-blue-500 transition-all duration-300"
                                    style={{ width: `${jobStatus.progress}%` }}
                                />
                            </div>
                        )}
                        {jobStatus.status === 'completed' && (
                            <div>
                                <p className="text-xs text-gray-500 mt-2 mb-4 breaking-all">Model saved to: {jobStatus.model_path}</p>
                                <button
                                    onClick={() => setJobStatus(null)}
                                    className="w-full bg-white/10 hover:bg-white/20 text-white font-medium py-2 rounded-lg transition-colors border border-white/10"
                                >
                                    Start New Job
                                </button>
                            </div>
                        )}
                        {jobStatus.status === 'failed' && (
                            <div>
                                <p className="text-xs text-red-400 mt-2 mb-4">Error: {jobStatus.error}</p>
                                <button
                                    onClick={() => setJobStatus(null)}
                                    className="w-full bg-white/10 hover:bg-white/20 text-white font-medium py-2 rounded-lg transition-colors border border-white/10"
                                >
                                    Try Again
                                </button>
                            </div>
                        )}
                    </div>
                ) : (
                    <button
                        onClick={startTraining}
                        disabled={loading}
                        className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-lg shadow-lg shadow-blue-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? 'Starting...' : 'Start Fine-Tuning Job'}
                    </button>
                )}
            </div>
        </div>
    )
}

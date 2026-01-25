import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';

export function ModelsInterface() {
    const [models, setModels] = useState<any[]>([]);
    const [activeTab, setActiveTab] = useState<'foundation' | 'custom'>('foundation')
    const [loading, setLoading] = useState(false);
    const [downloading, setDownloading] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);

    // Custom Model State
    const [showAddModal, setShowAddModal] = useState(false);
    const [customName, setCustomName] = useState("");
    const [customPath, setCustomPath] = useState("");
    const [customUrl, setCustomUrl] = useState("");

    // Filtering State
    const [searchQuery, setSearchQuery] = useState("");
    const [familyFilter, setFamilyFilter] = useState("All");
    const FAMILIES = ["All", "Llama", "Qwen", "Gemma", "Mistral", "DeepSeek"];

    useEffect(() => {
        const interval = setInterval(() => {
            fetchModels(true)
        }, 2000)
        return () => clearInterval(interval)
    }, [])

    const [systemStats, setSystemStats] = useState<any>(null);

    useEffect(() => {
        fetchModels();
        // Fetch system stats for compatibility check
        apiClient.monitor.getStats().then(setSystemStats).catch(console.error);
    }, []);

    const fetchModels = async (silent = false) => {
        try {
            if (!silent) setLoading(true);
            const data = await apiClient.engine.getModels();
            setModels(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            if (!silent) setLoading(false);
        }
    };

    // Helper to check if model fits in RAM (with 20% overhead buffer)
    const checkCompatibility = (sizeStr: string): { compatible: boolean, required: string } | null => {
        if (!systemStats || !sizeStr) return null;

        try {
            const sizeValue = parseFloat(sizeStr.replace(/[^0-9.]/g, ''));
            const isGB = sizeStr.toUpperCase().includes('GB');
            const isMB = sizeStr.toUpperCase().includes('MB');

            let sizeBytes = 0;
            if (isGB) sizeBytes = sizeValue * 1024 * 1024 * 1024;
            else if (isMB) sizeBytes = sizeValue * 1024 * 1024;
            else return null;

            const safeLimit = systemStats.memory.total; // Total RAM
            const requiredBytes = sizeBytes * 1.2; // 20% overhead (OS + Context)

            return {
                compatible: requiredBytes <= safeLimit,
                required: (requiredBytes / (1024 * 1024 * 1024)).toFixed(1) + " GB"
            };
        } catch (e) {
            return null;
        }
    };

    const foundationModels = models.filter(m => {
        if (m.is_finetuned) return false; // Only exclude fine-tuned models

        const matchesSearch = m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            m.id.toLowerCase().includes(searchQuery.toLowerCase());

        let matchesFamily = false;
        if (familyFilter === "All") {
            matchesFamily = true;
        } else if (familyFilter === "Mistral") {
            // Special handling for Mistral/Mixtral
            matchesFamily = m.name.toLowerCase().includes("mistral") || m.name.toLowerCase().includes("mixtral");
        } else {
            matchesFamily = m.name.toLowerCase().includes(familyFilter.toLowerCase());
        }

        return matchesSearch && matchesFamily;
    })
    const customModels = models.filter(m => m.is_finetuned) // Only show fine-tuned models in Custom tab

    const handleDownload = async (modelId: string) => {
        try {
            setDownloading(prev => new Set(prev).add(modelId));
            await apiClient.engine.downloadModel(modelId);

            // Poll until the model shows as downloaded
            const pollForCompletion = async () => {
                const data = await apiClient.engine.getModels();
                const model = data.find((m: any) => m.id === modelId);
                if (model?.downloaded) {
                    setModels(data);
                    setDownloading(prev => {
                        const next = new Set(prev);
                        next.delete(modelId);
                        return next;
                    });
                } else {
                    setTimeout(pollForCompletion, 1000);
                }
            };
            pollForCompletion();
        } catch (err: any) {
            alert(`Failed to start download: ${err.message}`);
            setDownloading(prev => {
                const next = new Set(prev);
                next.delete(modelId);
                return next;
            });
        }
    };

    const [modelToDelete, setModelToDelete] = useState<any | null>(null);

    const handleDelete = async () => {
        if (!modelToDelete) return;
        try {
            setLoading(true);
            await apiClient.engine.deleteModel(modelToDelete.id);
            await fetchModels();
            setModelToDelete(null);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const handleRegister = async () => {
        if (!customName || !customPath) return;
        try {
            setLoading(true);
            await apiClient.engine.registerModel(customName, customPath, customUrl);
            await fetchModels();
            setShowAddModal(false);
            setCustomName("");
            setCustomPath("");
            setCustomUrl("");
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="h-full flex flex-col pt-8 px-8 pb-0 bg-[#111111] text-white overflow-hidden">
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Models</h1>
                    <p className="text-gray-400 mt-1">Manage your local LLM library</p>
                </div>
                <div className="flex gap-4">
                    {activeTab === 'foundation' && (
                        <button
                            onClick={() => setShowAddModal(true)}
                            className="bg-white/10 hover:bg-white/20 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors border border-white/5"
                        >
                            + Add Foundation Model
                        </button>
                    )}
                </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-6 mb-6 border-b border-white/10">
                <button
                    onClick={() => setActiveTab('foundation')}
                    className={`pb-3 text-sm font-medium transition-colors relative ${activeTab === 'foundation' ? 'text-blue-400' : 'text-gray-400 hover:text-white'}`}
                >
                    Foundation Models
                    {activeTab === 'foundation' && <div className="absolute bottom-0 left-0 w-full h-0.5 bg-blue-400"></div>}
                </button>
                <button
                    onClick={() => setActiveTab('custom')}
                    className={`pb-3 text-sm font-medium transition-colors relative ${activeTab === 'custom' ? 'text-blue-400' : 'text-gray-400 hover:text-white'}`}
                >
                    Custom Models
                    {activeTab === 'custom' && <div className="absolute bottom-0 left-0 w-full h-0.5 bg-blue-400"></div>}
                </button>
            </div>

            {/* Filters (Foundation Only) */}
            {activeTab === 'foundation' && (
                <div className="flex flex-col md:flex-row gap-4 mb-6">
                    <div className="relative flex-1">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <svg className="h-4 w-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        </div>
                        <input
                            type="text"
                            placeholder="Search models..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white outline-none focus:border-blue-500 text-sm placeholder-gray-600 transition-colors hover:bg-white/10"
                        />
                    </div>
                    <div className="flex gap-2 overflow-x-auto pb-2 md:pb-0 no-scrollbar">
                        {FAMILIES.map(family => (
                            <button
                                key={family}
                                onClick={() => setFamilyFilter(family)}
                                className={`px-4 py-2 rounded-lg text-sm font-medium border transition-all whitespace-nowrap ${familyFilter === family
                                    ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-500/20'
                                    : 'bg-white/5 border-white/10 text-gray-400 hover:bg-white/10 hover:text-white'
                                    }`}
                            >
                                {family}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {error && (
                <div className="mb-4 bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-lg text-sm flex justify-between items-center">
                    <span>{error}</span>
                    <button onClick={() => setError(null)} className="text-white/40 hover:text-white">✕</button>
                </div>
            )}

            <div className="flex-1 overflow-y-auto pr-2 pb-8">
                {activeTab === 'foundation' ? (
                    <div className="grid grid-cols-1 gap-4">
                        {foundationModels.map((model) => {
                            const isDownloading = downloading.has(model.id) || model.downloading;
                            const compatibility = checkCompatibility(model.size);

                            return (
                                <div key={model.id} className="bg-white/5 border border-white/10 rounded-xl p-6 flex items-center justify-between hover:bg-white/[0.07] transition-colors group">
                                    <div className="flex items-center gap-4">
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <h3 className="font-semibold text-lg">{model.name}</h3>

                                                {/* Compatibility Warning */}
                                                {compatibility && !compatibility.compatible && (
                                                    <div className="group/compat relative">
                                                        <span className="text-red-400 bg-red-500/10 border border-red-500/20 rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold cursor-help">
                                                            !
                                                        </span>
                                                        <div className="absolute left-full ml-2 top-1/2 -translate-y-1/2 w-48 bg-black/90 border border-red-500/30 text-xs text-white p-2 rounded-lg shadow-xl opacity-0 group-hover/compat:opacity-100 pointer-events-none transition-opacity z-10">
                                                            <p className="font-bold text-red-300 mb-1">High RAM Warning</p>
                                                            Requires ~{compatibility.required} RAM (Available: {systemStats ? (systemStats.memory.total / (1024 * 1024 * 1024)).toFixed(0) + " GB" : "?"})
                                                        </div>
                                                    </div>
                                                )}

                                                {model.is_custom ? (
                                                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/20 uppercase font-bold tracking-wider">
                                                        User
                                                    </span>
                                                ) : (
                                                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/20 uppercase font-bold tracking-wider">
                                                        Default
                                                    </span>
                                                )}

                                                {model.size !== 'Custom' && (
                                                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-gray-400 border border-white/5">
                                                        {model.size}
                                                    </span>
                                                )}

                                                {/* Hugging Face Link */}
                                                {model.url && (
                                                    <a
                                                        href={model.url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="text-[10px] px-2 py-0.5 rounded-full bg-yellow-500/10 text-yellow-500 border border-yellow-500/20 uppercase font-bold tracking-wider hover:bg-yellow-500/20 transition-colors flex items-center gap-1"
                                                        title={model.url}
                                                    >
                                                        hf ↗
                                                    </a>
                                                )}
                                            </div>
                                            <p className="text-sm text-gray-500 font-mono mt-1">{model.id}</p>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-4">
                                        {isDownloading ? (
                                            <div className="w-[176px] h-10 flex items-center justify-center gap-2 bg-yellow-500/10 text-yellow-500 rounded-lg border border-yellow-500/20">
                                                <div className="w-4 h-4 border-2 border-yellow-500/30 border-t-yellow-500 rounded-full animate-spin" />
                                                <span className="text-sm font-medium">Downloading</span>
                                            </div>
                                        ) : model.downloaded ? (
                                            <div className="flex items-center gap-2">
                                                <div className="w-32 h-10 flex items-center justify-center gap-2 bg-green-500/10 text-green-500 rounded-lg border border-green-500/20 cursor-default">
                                                    <span className="text-sm font-bold">✓ Ready</span>
                                                </div>
                                                <button
                                                    onClick={() => setModelToDelete(model)}
                                                    className="w-10 h-10 flex items-center justify-center rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-colors"
                                                    title="Delete Model"
                                                >
                                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                                    </svg>
                                                </button>
                                            </div>
                                        ) : (
                                            <button
                                                onClick={() => handleDownload(model.id)}
                                                className="w-[176px] h-10 bg-white text-black font-semibold rounded-lg hover:bg-gray-200 transition-colors"
                                            >
                                                Download
                                            </button>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {customModels.length === 0 && (
                            <div className="col-span-2 text-center py-20 text-gray-500">
                                <p className="text-lg mb-2">No custom models found.</p>
                                <p className="text-sm opacity-60">Fine-tune a model in the Engine tab to see it here.</p>
                            </div>
                        )}
                        {customModels.map((model) => (
                            <div key={model.id} className="bg-white/5 border border-white/10 rounded-xl p-6 hover:bg-white/[0.07] transition-colors relative group">
                                <div className="flex justify-between items-start mb-4">
                                    <div className="flex items-center gap-3">
                                        <div>
                                            <h3 className="font-semibold text-lg">{model.name}</h3>
                                            <p className="text-xs text-gray-500">
                                                Based on: <span className="text-gray-400">{model.base_model || 'Unknown'}</span>
                                            </p>
                                        </div>
                                    </div>
                                    <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/20 uppercase font-bold tracking-wider whitespace-nowrap flex-shrink-0">
                                        Fine-Tuned
                                    </span>
                                </div>

                                {model.params && (
                                    <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-xs text-gray-400 mb-4 bg-black/20 p-3 rounded-lg border border-white/5">
                                        <div className="flex justify-between"><span>Epochs:</span> <span className="text-white font-mono">{model.params.epochs}</span></div>
                                        <div className="flex justify-between"><span>Batch Size:</span> <span className="text-white font-mono">{model.params.batch_size}</span></div>
                                        <div className="flex justify-between"><span>Rank:</span> <span className="text-white font-mono">{model.params.lora_rank}</span></div>
                                        <div className="flex justify-between"><span>Alpha:</span> <span className="text-white font-mono">{model.params.lora_alpha}</span></div>
                                        <div className="flex justify-between"><span>LR:</span> <span className="text-white font-mono">{model.params.learning_rate}</span></div>
                                        <div className="flex justify-between"><span>Dropout:</span> <span className="text-white font-mono">{model.params.dropout}</span></div>
                                        <div className="flex justify-between"><span>Seq Len:</span> <span className="text-white font-mono">{model.params.max_seq_len || 'N/A'}</span></div>
                                        <div className="flex justify-between"><span>Layers:</span> <span className="text-white font-mono">{model.params.lora_layers || 'N/A'}</span></div>
                                    </div>
                                )}

                                <div className="text-[10px] font-mono text-gray-600 truncate mb-4 select-all" title={model.adapter_path || model.id}>
                                    Adapter: {model.adapter_path ? model.adapter_path.split('/').pop() : 'N/A'}
                                </div>

                                <div className="absolute bottom-4 right-4">
                                    <button
                                        onClick={() => setModelToDelete(model)}
                                        className="px-3 py-2 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-colors"
                                        title="Delete Model"
                                    >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                        </svg>
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Confirmation Modal */}
            {modelToDelete && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                    <div className="bg-[#1E1E1E] border border-white/10 rounded-xl max-w-sm w-full p-6 shadow-2xl transform transition-all scale-100">
                        <h3 className="text-lg font-bold text-white mb-2">Delete Model?</h3>
                        <p className="text-gray-400 text-sm mb-6">
                            Are you sure you want to delete <span className="text-white font-medium">{modelToDelete.name}</span>?
                            This will remove the downloaded files from your disk.
                        </p>
                        <div className="flex justify-end gap-3">
                            <button
                                onClick={() => setModelToDelete(null)}
                                className="px-4 py-2 rounded-lg text-sm font-medium text-gray-300 hover:bg-white/5 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleDelete}
                                className="px-4 py-2 rounded-lg text-sm font-medium bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-500/20 transition-all"
                            >
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Add Foundation Model Modal */}
            {showAddModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
                    <div className="bg-[#1E1E1E] border border-white/10 rounded-xl max-w-md w-full p-6 shadow-2xl transform transition-all scale-100">
                        <h3 className="text-lg font-bold text-white mb-4">Add Foundation Model</h3>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-xs uppercase text-gray-500 font-semibold mb-1">Model Name</label>
                                <input
                                    type="text"
                                    value={customName}
                                    onChange={(e) => setCustomName(e.target.value)}
                                    placeholder="e.g. My Llama Finetune"
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-white outline-none focus:border-blue-500 text-sm"
                                />
                            </div>

                            <div>
                                <label className="block text-xs uppercase text-gray-500 font-semibold mb-1">Hugging Face URL (Optional)</label>
                                <input
                                    type="text"
                                    value={customUrl}
                                    onChange={(e) => setCustomUrl(e.target.value)}
                                    placeholder="https://huggingface.co/..."
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-white outline-none focus:border-blue-500 text-sm"
                                />
                                <p className="text-[10px] text-white/30 mt-1">For reference only.</p>
                            </div>

                            <div>
                                <label className="block text-xs uppercase text-gray-500 font-semibold mb-1">Model Folder Path</label>
                                <div className="flex gap-2">
                                    <input
                                        type="text"
                                        value={customPath}
                                        readOnly
                                        placeholder="/path/to/extracted/model"
                                        className="flex-1 bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-white outline-none focus:border-blue-500 text-sm opacity-70"
                                    />
                                    <button
                                        onClick={async () => {
                                            const path = await (window as any).electronAPI.selectDirectory();
                                            if (path) setCustomPath(path);
                                        }}
                                        className="bg-white/10 hover:bg-white/20 text-white px-3 py-2 rounded-lg transition-colors text-sm"
                                    >
                                        📂
                                    </button>
                                </div>
                                <p className="text-[10px] text-white/40 mt-1">
                                    This absolute path will be used as the <strong>Model ID</strong>.
                                </p>
                            </div>
                        </div>

                        <div className="flex justify-end gap-3 mt-6">
                            <button
                                onClick={() => setShowAddModal(false)}
                                className="px-4 py-2 rounded-lg text-sm font-medium text-gray-300 hover:bg-white/5 transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleRegister}
                                disabled={!customName || !customPath || loading}
                                className="px-4 py-2 rounded-lg text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20 transition-all disabled:opacity-50"
                            >
                                Register Model
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Download, Trash2, RefreshCw, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import type { OllamaModel } from '../lib/types';

export function OllamaModels() {
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [newModelName, setNewModelName] = useState('');
  const [pulling, setPulling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadModels = async () => {
    setLoading(true);
    try {
      const result = await invoke<OllamaModel[]>('list_ollama_models');
      setModels(result);
      setError(null);
    } catch (err) {
      setError(`Failed to load models: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadModels();
  }, []);

  const pullModel = async () => {
    if (!newModelName.trim()) return;

    setPulling(true);
    try {
      await invoke('pull_ollama_model', { modelName: newModelName });
      setNewModelName('');
      await loadModels();
    } catch (err) {
      setError(`Failed to pull model: ${err}`);
    } finally {
      setPulling(false);
    }
  };

  const deleteModel = async (name: string) => {
    if (!confirm(`Delete model "${name}"? This cannot be undone.`)) return;

    try {
      await invoke('delete_ollama_model', { modelName: name });
      await loadModels();
    } catch (err) {
      setError(`Failed to delete model: ${err}`);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Ollama Models</h1>

      {error && (
        <div className="bg-red-900/30 border border-red-700 text-red-400 p-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Pull New Model */}
      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="text-lg font-semibold text-white mb-3">Pull New Model</h3>
        <div className="flex gap-3">
          <input
            type="text"
            value={newModelName}
            onChange={(e) => setNewModelName(e.target.value)}
            placeholder="e.g., llama3.2, qwen2.5:14b, deepseek-r1:14b"
            className="flex-1 bg-gray-700 px-3 py-2 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={pulling}
            onKeyDown={(e) => e.key === 'Enter' && pullModel()}
          />
          <button
            onClick={pullModel}
            disabled={pulling || !newModelName.trim()}
            className={clsx(
              'px-4 py-2 rounded-lg flex items-center gap-2 font-medium',
              pulling || !newModelName.trim()
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-700 text-white'
            )}
          >
            {pulling ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            {pulling ? 'Pulling...' : 'Pull'}
          </button>
        </div>
        <p className="text-sm text-gray-400 mt-2">
          Pull models from the Ollama registry. This may take a while for large models.
        </p>
      </div>

      {/* Model List */}
      <div className="bg-gray-800 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold text-white">Installed Models</h3>
          <button
            onClick={loadModels}
            disabled={loading}
            className="p-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg disabled:opacity-50"
          >
            <RefreshCw className={clsx("w-4 h-4", loading && "animate-spin")} />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
          </div>
        ) : models.length === 0 ? (
          <p className="text-gray-400 py-4">No models installed. Pull a model to get started.</p>
        ) : (
          <div className="space-y-2">
            {models.map((model) => (
              <div
                key={model.name}
                className="flex items-center justify-between p-3 bg-gray-700 rounded-lg"
              >
                <div>
                  <p className="font-medium text-white">{model.name}</p>
                  <p className="text-sm text-gray-400">
                    {model.size} • {model.modified}
                  </p>
                </div>
                <button
                  onClick={() => deleteModel(model.name)}
                  className="p-2 text-red-400 hover:bg-red-900/30 rounded-lg"
                  title="Delete model"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Model Usage Info */}
      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="text-lg font-semibold text-white mb-2">Model Recommendations</h3>
        <div className="space-y-2 text-sm text-gray-400">
          <p><span className="text-white">qwen2.5:14b</span> - Best for complex reasoning and code</p>
          <p><span className="text-white">deepseek-r1:14b</span> - Strong reasoning capabilities</p>
          <p><span className="text-white">llama3.2</span> - Fast for simple tasks</p>
          <p><span className="text-white">nomic-embed-text</span> - Text embeddings for RAG</p>
        </div>
      </div>
    </div>
  );
}

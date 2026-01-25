import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Save, Plus, Trash2, AlertCircle, CheckCircle, RefreshCw, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import type { Config, RoutingPolicy, ValidationResult, ModelConfig } from '../lib/types';

export function ConfigEditor() {
  const [config, setConfig] = useState<Config | null>(null);
  const [policy, setPolicy] = useState<RoutingPolicy | null>(null);
  const [activeTab, setActiveTab] = useState<'models' | 'routing'>('models');
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const [configData, policyData] = await Promise.all([
        invoke<Config>('read_config'),
        invoke<RoutingPolicy>('read_policy'),
      ]);
      setConfig(configData);
      setPolicy(policyData);
      setDirty(false);
      setError(null);
    } catch (err) {
      setError(`Failed to load config: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const validateAndSave = async () => {
    if (!config || !policy) return;

    setSaving(true);
    try {
      const result = await invoke<ValidationResult>('validate_config', { config });
      setValidation(result);

      if (result.valid) {
        await invoke('write_config', { config });
        await invoke('write_policy', { policy });
        setDirty(false);
        setError(null);
      }
    } catch (err) {
      setError(`Failed to save config: ${err}`);
    } finally {
      setSaving(false);
    }
  };

  const updateModel = (index: number, field: keyof ModelConfig | 'model' | 'api_base', value: string) => {
    if (!config) return;
    const newConfig = { ...config, model_list: [...config.model_list] };
    const model = { ...newConfig.model_list[index] };

    if (field === 'model_name') {
      model.model_name = value;
    } else if (field === 'model') {
      model.litellm_params = { ...model.litellm_params, model: value };
    } else if (field === 'api_base') {
      model.litellm_params = { ...model.litellm_params, api_base: value };
    }

    newConfig.model_list[index] = model;
    setConfig(newConfig);
    setDirty(true);
  };

  const addModel = () => {
    if (!config) return;
    const newConfig = { ...config };
    newConfig.model_list = [
      ...newConfig.model_list,
      {
        model_name: 'new-model',
        litellm_params: {
          model: 'ollama/model-name',
          api_base: 'http://localhost:11434',
        },
      },
    ];
    setConfig(newConfig);
    setDirty(true);
  };

  const removeModel = (index: number) => {
    if (!config) return;
    const newConfig = { ...config };
    newConfig.model_list = newConfig.model_list.filter((_, i) => i !== index);
    setConfig(newConfig);
    setDirty(true);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="w-8 h-8 text-gray-400 animate-spin" />
      </div>
    );
  }

  if (error && !config) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Configuration</h1>
        <div className="bg-red-900/30 border border-red-700 text-red-400 p-4 rounded-lg">
          {error}
        </div>
      </div>
    );
  }

  if (!config || !policy) {
    return <div className="text-gray-400">Loading configuration...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Configuration</h1>
        <div className="flex items-center gap-3">
          {dirty && (
            <span className="text-yellow-400 text-sm">Unsaved changes</span>
          )}
          <button
            onClick={loadConfig}
            className="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg flex items-center gap-2 text-gray-300"
          >
            <RefreshCw className="w-4 h-4" />
            Reload
          </button>
          <button
            onClick={validateAndSave}
            disabled={saving || !dirty}
            className={clsx(
              'px-4 py-2 rounded-lg flex items-center gap-2 font-medium',
              dirty
                ? 'bg-blue-600 hover:bg-blue-700 text-white'
                : 'bg-gray-700 text-gray-500 cursor-not-allowed'
            )}
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {/* Validation Messages */}
      {validation && (
        <div className="space-y-2">
          {validation.errors.map((err, i) => (
            <div key={i} className="flex items-center gap-2 text-red-400 bg-red-900/20 p-3 rounded-lg">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              {err}
            </div>
          ))}
          {validation.warnings.map((warning, i) => (
            <div key={i} className="flex items-center gap-2 text-yellow-400 bg-yellow-900/20 p-3 rounded-lg">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              {warning}
            </div>
          ))}
          {validation.valid && validation.errors.length === 0 && (
            <div className="flex items-center gap-2 text-green-400 bg-green-900/20 p-3 rounded-lg">
              <CheckCircle className="w-5 h-5" />
              Configuration is valid
            </div>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-700 pb-2">
        {(['models', 'routing'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              'px-4 py-2 rounded-t-lg font-medium',
              activeTab === tab
                ? 'bg-gray-800 text-white'
                : 'text-gray-400 hover:text-white'
            )}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Models Tab */}
      {activeTab === 'models' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white">Model Configuration</h2>
            <button
              onClick={addModel}
              className="px-3 py-1.5 bg-green-600 hover:bg-green-700 rounded-lg flex items-center gap-1 text-sm text-white"
            >
              <Plus className="w-4 h-4" />
              Add Model
            </button>
          </div>

          {config.model_list.map((model, index) => (
            <div key={index} className="bg-gray-800 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <input
                  type="text"
                  value={model.model_name}
                  onChange={(e) => updateModel(index, 'model_name', e.target.value)}
                  className="bg-gray-700 px-3 py-2 rounded-lg font-medium text-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Model alias"
                />
                <button
                  onClick={() => removeModel(index)}
                  className="p-2 text-red-400 hover:bg-red-900/30 rounded-lg"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm text-gray-400 block mb-1">Provider/Model</label>
                  <input
                    type="text"
                    value={model.litellm_params.model}
                    onChange={(e) => updateModel(index, 'model', e.target.value)}
                    className="w-full bg-gray-700 px-3 py-2 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="ollama/model-name"
                  />
                </div>
                <div>
                  <label className="text-sm text-gray-400 block mb-1">API Base URL</label>
                  <input
                    type="text"
                    value={model.litellm_params.api_base}
                    onChange={(e) => updateModel(index, 'api_base', e.target.value)}
                    className="w-full bg-gray-700 px-3 py-2 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="http://localhost:11434"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Routing Tab */}
      {activeTab === 'routing' && (
        <div className="space-y-6">
          {/* Privacy Settings */}
          <div className="bg-gray-800 rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">Privacy Detection</h3>
              <label className="flex items-center gap-2 text-gray-300">
                <input
                  type="checkbox"
                  checked={policy.privacy.enabled}
                  onChange={(e) => {
                    const newPolicy = { ...policy, privacy: { ...policy.privacy, enabled: e.target.checked } };
                    setPolicy(newPolicy);
                    setDirty(true);
                  }}
                  className="w-4 h-4 rounded"
                />
                Enabled
              </label>
            </div>

            <div>
              <label className="text-sm text-gray-400 block mb-1">Entropy Threshold</label>
              <input
                type="number"
                step="0.1"
                value={policy.privacy.entropy_threshold}
                onChange={(e) => {
                  const newPolicy = { ...policy, privacy: { ...policy.privacy, entropy_threshold: parseFloat(e.target.value) || 0 } };
                  setPolicy(newPolicy);
                  setDirty(true);
                }}
                className="w-full bg-gray-700 px-3 py-2 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-500 mt-1">Higher values detect more potential secrets</p>
            </div>

            {/* PII Patterns */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-gray-400">PII Detection Patterns (regex)</label>
                <button
                  onClick={() => {
                    const newPolicy = {
                      ...policy,
                      privacy: {
                        ...policy.privacy,
                        pii_regexes: [...policy.privacy.pii_regexes, '(?i)new_pattern'],
                      },
                    };
                    setPolicy(newPolicy);
                    setDirty(true);
                  }}
                  className="text-sm text-blue-400 hover:text-blue-300"
                >
                  + Add Pattern
                </button>
              </div>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {policy.privacy.pii_regexes.map((pattern, index) => (
                  <div key={index} className="flex gap-2">
                    <input
                      type="text"
                      value={pattern}
                      onChange={(e) => {
                        const newPatterns = [...policy.privacy.pii_regexes];
                        newPatterns[index] = e.target.value;
                        const newPolicy = { ...policy, privacy: { ...policy.privacy, pii_regexes: newPatterns } };
                        setPolicy(newPolicy);
                        setDirty(true);
                      }}
                      className="flex-1 bg-gray-700 px-3 py-2 rounded-lg font-mono text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      onClick={() => {
                        const newPatterns = policy.privacy.pii_regexes.filter((_, i) => i !== index);
                        const newPolicy = { ...policy, privacy: { ...policy.privacy, pii_regexes: newPatterns } };
                        setPolicy(newPolicy);
                        setDirty(true);
                      }}
                      className="p-2 text-red-400 hover:bg-red-900/30 rounded-lg"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Complexity Settings */}
          <div className="bg-gray-800 rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">Complexity Routing</h3>
              <label className="flex items-center gap-2 text-gray-300">
                <input
                  type="checkbox"
                  checked={policy.complexity.enabled}
                  onChange={(e) => {
                    const newPolicy = { ...policy, complexity: { ...policy.complexity, enabled: e.target.checked } };
                    setPolicy(newPolicy);
                    setDirty(true);
                  }}
                  className="w-4 h-4 rounded"
                />
                Enabled
              </label>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-gray-400 block mb-1">Simple Max Tokens</label>
                <input
                  type="number"
                  value={policy.complexity.simple_max_tokens}
                  onChange={(e) => {
                    const newPolicy = { ...policy, complexity: { ...policy.complexity, simple_max_tokens: parseInt(e.target.value) || 0 } };
                    setPolicy(newPolicy);
                    setDirty(true);
                  }}
                  className="w-full bg-gray-700 px-3 py-2 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="text-sm text-gray-400 block mb-1">Medium Max Tokens</label>
                <input
                  type="number"
                  value={policy.complexity.medium_max_tokens}
                  onChange={(e) => {
                    const newPolicy = { ...policy, complexity: { ...policy.complexity, medium_max_tokens: parseInt(e.target.value) || 0 } };
                    setPolicy(newPolicy);
                    setDirty(true);
                  }}
                  className="w-full bg-gray-700 px-3 py-2 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>

          {/* Injection Detection */}
          <div className="bg-gray-800 rounded-lg p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">Injection Detection</h3>
              <label className="flex items-center gap-2 text-gray-300">
                <input
                  type="checkbox"
                  checked={policy.injection.enabled}
                  onChange={(e) => {
                    const newPolicy = { ...policy, injection: { ...policy.injection, enabled: e.target.checked } };
                    setPolicy(newPolicy);
                    setDirty(true);
                  }}
                  className="w-4 h-4 rounded"
                />
                Enabled
              </label>
            </div>

            <label className="flex items-center gap-2 text-gray-300">
              <input
                type="checkbox"
                checked={policy.injection.block_on_injection}
                onChange={(e) => {
                  const newPolicy = { ...policy, injection: { ...policy.injection, block_on_injection: e.target.checked } };
                  setPolicy(newPolicy);
                  setDirty(true);
                }}
                className="w-4 h-4 rounded"
              />
              Block requests on injection detection
            </label>
            <p className="text-xs text-gray-500">When enabled, suspected injection attempts will be blocked instead of just logged</p>

            {/* Injection Patterns */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm text-gray-400">Injection Patterns (regex)</label>
                <button
                  onClick={() => {
                    const newPolicy = {
                      ...policy,
                      injection: {
                        ...policy.injection,
                        patterns: [...policy.injection.patterns, '(?i)new_pattern'],
                      },
                    };
                    setPolicy(newPolicy);
                    setDirty(true);
                  }}
                  className="text-sm text-blue-400 hover:text-blue-300"
                >
                  + Add Pattern
                </button>
              </div>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {policy.injection.patterns.map((pattern, index) => (
                  <div key={index} className="flex gap-2">
                    <input
                      type="text"
                      value={pattern}
                      onChange={(e) => {
                        const newPatterns = [...policy.injection.patterns];
                        newPatterns[index] = e.target.value;
                        const newPolicy = { ...policy, injection: { ...policy.injection, patterns: newPatterns } };
                        setPolicy(newPolicy);
                        setDirty(true);
                      }}
                      className="flex-1 bg-gray-700 px-3 py-2 rounded-lg font-mono text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      onClick={() => {
                        const newPatterns = policy.injection.patterns.filter((_, i) => i !== index);
                        const newPolicy = { ...policy, injection: { ...policy.injection, patterns: newPatterns } };
                        setPolicy(newPolicy);
                        setDirty(true);
                      }}
                      className="p-2 text-red-400 hover:bg-red-900/30 rounded-lg"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

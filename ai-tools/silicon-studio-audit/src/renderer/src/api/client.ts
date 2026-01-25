const API_BASE = 'http://127.0.0.1:8000';

export interface SystemStats {
    memory: {
        total: number;
        available: number;
        used: number;
        percent: number;
    };
    cpu: {
        percent: number;
        cores: number;
    };
    disk: {
        percent: number;
    };
}

export interface PreviewRow {
    instruction: string;
    input: string;
    output: string;
    [key: string]: string;
}

export const apiClient = {
    monitor: {
        getStats: async (): Promise<SystemStats> => {
            const res = await fetch(`${API_BASE}/api/monitor/stats`);
            if (!res.ok) throw new Error('Failed to fetch system stats');
            return res.json();
        }
    },
    preparation: {
        previewCsv: async (filePath: string, limit: number = 5): Promise<{ data: PreviewRow[] }> => {
            const res = await fetch(`${API_BASE}/api/preparation/preview`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_path: filePath, limit })
            });
            if (!res.ok) throw new Error('Failed to preview CSV');
            return res.json();
        },
        convertCsv: async (file_path: string, output_path: string, instruction_col: string, input_col: string | undefined, output_col: string, strip_pii: boolean, model_family: string): Promise<any> => {
            const res = await fetch(`${API_BASE}/api/preparation/convert`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_path,
                    output_path,
                    instruction_col,
                    input_col,
                    output_col,
                    strip_pii,
                    model_family
                })
            });
            if (!res.ok) throw new Error('Failed to convert CSV');
            return res.json();
        }
    },
    shield: {
        redact: async (text: string): Promise<any> => {
            const res = await fetch(`${API_BASE}/api/shield/redact`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text })
            });
            if (!res.ok) throw new Error('Failed to redact text');
            return res.json();
        }
    },
    engine: {
        getModels: async (): Promise<any[]> => {
            const res = await fetch(`${API_BASE}/api/engine/models`);
            if (!res.ok) throw new Error('Failed to list models');
            return res.json();
        },
        downloadModel: async (modelId: string): Promise<any> => {
            const res = await fetch(`${API_BASE}/api/engine/models/download`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId })
            });
            if (!res.ok) throw new Error('Failed to start download');
            return res.json();
        },
        deleteModel: async (modelId: string): Promise<any> => {
            const res = await fetch(`${API_BASE}/api/engine/models/delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId })
            });
            if (!res.ok) throw new Error('Failed to delete model');
            return res.json();
        },
        registerModel: async (name: string, path: string, url: string = ""): Promise<any> => {
            const res = await fetch(`${API_BASE}/api/engine/models/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, path, url })
            });
            if (!res.ok) throw new Error('Failed to register model');
            return res.json();
        },
        finetune: async (config: any): Promise<any> => {
            const res = await fetch(`${API_BASE}/api/engine/finetune`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            if (!res.ok) throw new Error('Failed to start fine-tuning');
            return res.json();
        },
        getJobStatus: async (jobId: string): Promise<any> => {
            const res = await fetch(`${API_BASE}/api/engine/jobs/${jobId}`);
            if (!res.ok) throw new Error('Failed to get job status');
            return res.json();
        },
        chat: async (modelId: string, messages: any[]): Promise<any> => {
            const res = await fetch(`${API_BASE}/api/engine/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId, messages })
            });
            if (!res.ok) throw new Error('Failed to generate response');
            return res.json();
        }
    }
};


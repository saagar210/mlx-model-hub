-- ============================================================================
-- SIA - Self-Improving Agents Framework
-- Database Schema
-- ============================================================================

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For fuzzy text matching

-- ============================================================================
-- AGENTS TABLE
-- Central registry of all agent definitions and versions
-- ============================================================================

CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    description TEXT,
    type TEXT NOT NULL CHECK (type IN ('single', 'multi', 'workflow', 'meta')),

    -- Code (for self-modifying agents)
    code_module TEXT NOT NULL,               -- Python module path (e.g., 'sia.agents.decomposer')
    code_snapshot TEXT,                      -- Full source code snapshot
    code_hash TEXT NOT NULL,                 -- SHA256 for change detection
    original_code TEXT NOT NULL,             -- Baseline for rollback

    -- Prompts (DSPy-optimized)
    system_prompt TEXT,
    task_prompt_template TEXT,
    dspy_optimized_prompts JSONB DEFAULT '{}',

    -- Configuration
    config JSONB DEFAULT '{}',               -- Agent-specific settings
    max_retries INTEGER DEFAULT 3,
    timeout_seconds INTEGER DEFAULT 300,

    -- LLM preferences
    preferred_model TEXT DEFAULT 'qwen2.5:7b',
    fallback_models TEXT[] DEFAULT ARRAY['openrouter/qwen', 'deepseek', 'claude-3-haiku'],
    temperature FLOAT DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 4096,

    -- Skills this agent can use
    available_skills UUID[] DEFAULT '{}',

    -- Status
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'testing', 'retired', 'failed')),
    is_baseline BOOLEAN DEFAULT false,       -- Original human-written version
    parent_version_id UUID REFERENCES agents(id),

    -- Performance tracking
    total_executions INTEGER DEFAULT 0,
    successful_executions INTEGER DEFAULT 0,
    success_rate FLOAT GENERATED ALWAYS AS (
        CASE WHEN total_executions > 0
        THEN successful_executions::FLOAT / total_executions
        ELSE 0 END
    ) STORED,
    avg_execution_time_ms FLOAT DEFAULT 0,
    avg_tokens_used FLOAT DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_execution TIMESTAMPTZ,
    retired_at TIMESTAMPTZ,

    -- Constraints
    UNIQUE(name, version)
);

-- ============================================================================
-- EXECUTIONS TABLE
-- Complete history of all agent executions
-- ============================================================================

CREATE TABLE executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    -- Task details
    task_type TEXT NOT NULL,                 -- 'decomposition', 'research', 'code_gen', etc.
    task_description TEXT NOT NULL,
    task_params JSONB DEFAULT '{}',

    -- Input/Output
    input_data JSONB NOT NULL,
    output_data JSONB,
    intermediate_steps JSONB[] DEFAULT '{}', -- Array of {step_num, action, result, timestamp}

    -- Tool/Skill usage
    tools_called TEXT[] DEFAULT '{}',
    skills_used UUID[] DEFAULT '{}',

    -- Performance
    success BOOLEAN,
    partial_success BOOLEAN DEFAULT false,   -- For multi-step tasks
    error_message TEXT,
    error_type TEXT,                         -- 'timeout', 'llm_error', 'validation', 'runtime'
    error_traceback TEXT,

    -- Metrics
    execution_time_ms INTEGER,
    llm_latency_ms INTEGER,
    tokens_input INTEGER,
    tokens_output INTEGER,
    tokens_total INTEGER,
    cost_usd DECIMAL(10,6),

    -- Context used
    model_used TEXT,
    agent_version TEXT,
    code_hash TEXT,                          -- Which code version was used
    prompts_version TEXT,                    -- DSPy optimization version

    -- Memory references
    episodic_memory_ids UUID[] DEFAULT '{}',
    context_retrieved JSONB DEFAULT '{}',    -- What memory was retrieved

    -- Reproducibility
    random_seed INTEGER,
    temperature_used FLOAT,

    -- Timing
    queued_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Request metadata
    request_id TEXT,                         -- For tracing through system
    parent_execution_id UUID REFERENCES executions(id),  -- For sub-tasks
    root_execution_id UUID REFERENCES executions(id),    -- Original task

    -- Feedback (will be populated later)
    human_rating FLOAT,
    automated_rating FLOAT,

    -- Full-text search on task description
    task_fts tsvector GENERATED ALWAYS AS (
        to_tsvector('english', COALESCE(task_description, ''))
    ) STORED
);

-- ============================================================================
-- SKILLS TABLE
-- Reusable skills discovered from successful executions
-- ============================================================================

CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    category TEXT NOT NULL,                  -- 'web', 'file', 'data', 'code', 'reasoning', etc.
    subcategory TEXT,
    tags TEXT[] DEFAULT '{}',

    -- Implementation
    code TEXT NOT NULL,                      -- Python function code
    signature TEXT NOT NULL,                 -- Function signature for type checking
    input_schema JSONB NOT NULL,             -- JSON schema for inputs
    output_schema JSONB NOT NULL,            -- JSON schema for outputs

    -- Dependencies
    python_dependencies TEXT[] DEFAULT '{}', -- pip packages required
    skill_dependencies UUID[] DEFAULT '{}',  -- Other skills this uses

    -- Discovery metadata
    discovered_from UUID REFERENCES executions(id),
    extraction_method TEXT,                  -- 'manual', 'llm_extraction', 'refactoring'
    human_curated BOOLEAN DEFAULT false,

    -- Composition
    is_composite BOOLEAN DEFAULT false,
    component_skills UUID[] DEFAULT '{}',
    composition_logic TEXT,                  -- How components are combined

    -- Performance
    success_rate FLOAT DEFAULT 0.0,
    avg_execution_time_ms FLOAT,
    usage_count INTEGER DEFAULT 0,
    last_success TIMESTAMPTZ,
    last_failure TIMESTAMPTZ,
    failure_count INTEGER DEFAULT 0,

    -- Embeddings
    embedding vector(768),
    embedding_model TEXT DEFAULT 'nomic-embed-text-v1.5',

    -- Example usage
    example_inputs JSONB[] DEFAULT '{}',
    example_outputs JSONB[] DEFAULT '{}',
    documentation TEXT,

    -- Status
    status TEXT DEFAULT 'experimental' CHECK (status IN ('experimental', 'active', 'deprecated', 'broken')),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_used TIMESTAMPTZ,
    deprecated_at TIMESTAMPTZ
);

-- ============================================================================
-- EPISODIC MEMORY TABLE
-- Timestamped execution events for context retrieval
-- ============================================================================

CREATE TABLE episodic_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,

    -- Event details
    sequence_num INTEGER NOT NULL,           -- Order within execution
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    event_type TEXT NOT NULL,                -- 'task_start', 'step_complete', 'tool_call',
                                             -- 'skill_use', 'error', 'retry', 'success'

    -- Content
    description TEXT NOT NULL,
    details JSONB DEFAULT '{}',

    -- Context snapshot
    agent_state JSONB,                       -- Agent state at this moment
    memory_state JSONB,                      -- What was in working memory
    environment_state JSONB,                 -- Relevant env vars, files, etc.

    -- Embedding for retrieval
    content_for_embedding TEXT,              -- Combined text for embedding
    embedding vector(768),
    embedding_model TEXT DEFAULT 'nomic-embed-text-v1.5',

    -- Importance score (for retrieval prioritization)
    importance_score FLOAT DEFAULT 0.5,      -- 0-1, higher = more important

    -- Links
    related_skill_id UUID REFERENCES skills(id),
    related_fact_ids UUID[] DEFAULT '{}',

    UNIQUE(execution_id, sequence_num)
);

-- ============================================================================
-- SEMANTIC MEMORY TABLE
-- Facts, knowledge, and learned patterns
-- ============================================================================

CREATE TABLE semantic_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Content
    fact TEXT NOT NULL,
    fact_type TEXT NOT NULL,                 -- 'rule', 'constraint', 'pattern', 'anti-pattern',
                                             -- 'preference', 'domain_knowledge', 'tool_info'
    category TEXT,
    tags TEXT[] DEFAULT '{}',

    -- Confidence & Evidence
    confidence FLOAT DEFAULT 1.0,            -- 0-1, decays over time if not reinforced
    evidence_count INTEGER DEFAULT 1,
    supporting_executions UUID[] DEFAULT '{}',
    contradicting_executions UUID[] DEFAULT '{}',

    -- Source
    source TEXT NOT NULL,                    -- 'learned', 'configured', 'user_feedback', 'extracted'
    source_description TEXT,

    -- Embedding
    embedding vector(768),
    embedding_model TEXT DEFAULT 'nomic-embed-text-v1.5',

    -- Validity
    valid_from TIMESTAMPTZ DEFAULT NOW(),
    valid_until TIMESTAMPTZ,                 -- NULL = indefinitely valid
    superseded_by UUID REFERENCES semantic_memory(id),

    -- Access tracking
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMPTZ,
    usefulness_score FLOAT DEFAULT 0.5,      -- Based on whether retrievals helped

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- ============================================================================
-- IMPROVEMENT EXPERIMENTS TABLE
-- Track all attempts to improve agents
-- ============================================================================

CREATE TABLE improvement_experiments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    -- Experiment type
    improvement_type TEXT NOT NULL CHECK (improvement_type IN (
        'prompt_optimization',     -- DSPy MIPROv2/SIMBA
        'code_mutation',           -- Gödel Agent style
        'skill_learning',          -- New skill discovery
        'skill_composition',       -- Combining existing skills
        'config_tuning',           -- Hyperparameter adjustment
        'architecture_change'      -- Structural changes
    )),

    -- Hypothesis
    hypothesis TEXT NOT NULL,
    expected_improvement TEXT,

    -- Baseline
    baseline_agent_version TEXT,
    baseline_code_hash TEXT,
    baseline_prompts JSONB,
    baseline_metrics JSONB NOT NULL,         -- {success_rate, avg_time, generalization_score}

    -- Proposed change
    proposed_code TEXT,
    proposed_code_hash TEXT,
    proposed_prompts JSONB,
    proposed_config JSONB,
    change_description TEXT NOT NULL,
    change_diff TEXT,                        -- Unified diff format

    -- DSPy-specific
    dspy_optimizer TEXT,                     -- 'MIPROv2', 'SIMBA', 'BootstrapFewShot'
    dspy_config JSONB,
    dspy_training_examples INTEGER,
    dspy_trials INTEGER,

    -- Evaluation
    evaluation_metrics JSONB,                -- Same structure as baseline_metrics
    improvement_delta JSONB,                 -- {success_rate: +0.15, avg_time: -50ms}

    -- Statistical significance
    sample_size INTEGER,
    confidence_interval FLOAT,
    p_value FLOAT,
    is_statistically_significant BOOLEAN,

    -- Safety checks
    sandbox_test_passed BOOLEAN,
    regression_tests_passed BOOLEAN,
    security_check_passed BOOLEAN,

    -- Decision
    status TEXT DEFAULT 'proposed' CHECK (status IN (
        'proposed', 'approved_for_testing', 'testing',
        'evaluated', 'approved', 'rejected', 'deployed', 'rolled_back'
    )),
    decision_reason TEXT,
    decided_by TEXT,                         -- 'automated', 'human:<user_id>'

    -- A/B testing
    test_execution_ids UUID[] DEFAULT '{}',
    control_execution_ids UUID[] DEFAULT '{}',
    test_traffic_percentage FLOAT,

    -- Deployment
    deployed_at TIMESTAMPTZ,
    new_agent_version_id UUID REFERENCES agents(id),
    rollback_reason TEXT,
    rolled_back_at TIMESTAMPTZ,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    testing_started_at TIMESTAMPTZ,
    testing_completed_at TIMESTAMPTZ,
    decided_at TIMESTAMPTZ
);

-- ============================================================================
-- FEEDBACK TABLE
-- Human and automated feedback on executions
-- ============================================================================

CREATE TABLE feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,

    -- Source
    source TEXT NOT NULL CHECK (source IN ('human', 'automated', 'validation', 'comparison')),
    source_details TEXT,                     -- e.g., user ID or validation rule name

    -- Rating
    rating FLOAT NOT NULL CHECK (rating >= 0 AND rating <= 1),
    rating_type TEXT NOT NULL,               -- 'correctness', 'completeness', 'efficiency',
                                             -- 'quality', 'helpfulness', 'overall'

    -- Details
    feedback_text TEXT,
    annotations JSONB DEFAULT '{}',          -- Specific parts marked good/bad
    suggested_improvement TEXT,

    -- For comparison feedback
    compared_to_execution_id UUID REFERENCES executions(id),
    preference TEXT CHECK (preference IN ('this', 'other', 'tie')),

    -- Impact tracking
    led_to_improvement_id UUID REFERENCES improvement_experiments(id),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- DSPY OPTIMIZATION TABLE
-- Track DSPy prompt optimization runs
-- ============================================================================

CREATE TABLE dspy_optimizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    experiment_id UUID REFERENCES improvement_experiments(id),

    -- Optimizer config
    optimizer_type TEXT NOT NULL,            -- 'MIPROv2', 'SIMBA', 'BootstrapFewShot', 'COPRO'
    optimizer_config JSONB NOT NULL,         -- Full optimizer parameters

    -- Training data
    training_examples_count INTEGER NOT NULL,
    validation_examples_count INTEGER,
    training_data_source TEXT,               -- 'executions', 'manual', 'synthetic'

    -- Signatures optimized
    signatures_optimized TEXT[] NOT NULL,    -- List of DSPy signature names

    -- Results
    baseline_scores JSONB NOT NULL,          -- Per-signature scores
    optimized_scores JSONB NOT NULL,
    improvement_pct JSONB,                   -- Per-signature improvement
    overall_improvement_pct FLOAT,

    -- Optimized artifacts
    optimized_instructions JSONB,            -- New instruction text per signature
    optimized_demos JSONB,                   -- Selected few-shot examples
    bootstrapped_demos JSONB,                -- Generated demonstrations

    -- Process details
    num_trials INTEGER,
    best_trial_num INTEGER,
    trial_history JSONB[] DEFAULT '{}',      -- Score progression

    -- State
    status TEXT DEFAULT 'pending' CHECK (status IN (
        'pending', 'running', 'completed', 'failed', 'applied'
    )),
    error_message TEXT,

    -- Timestamps
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    applied_at TIMESTAMPTZ
);

-- ============================================================================
-- CODE EVOLUTION TABLE
-- Track code mutations (Gödel Agent style)
-- ============================================================================

CREATE TABLE code_evolutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    experiment_id UUID REFERENCES improvement_experiments(id),

    -- Evolution type
    evolution_type TEXT NOT NULL CHECK (evolution_type IN (
        'random_mutation',        -- Random code changes
        'llm_guided',             -- LLM proposes improvements
        'crossover',              -- Combine two agent versions
        'simplification',         -- Remove unnecessary code
        'refactoring',            -- Restructure without changing behavior
        'bug_fix'                 -- Fix identified issue
    )),

    -- Mutation details
    mutation_target TEXT,                    -- Which function/method
    mutation_description TEXT NOT NULL,

    -- Code
    original_code TEXT NOT NULL,
    mutated_code TEXT NOT NULL,
    diff TEXT NOT NULL,                      -- Unified diff

    -- LLM guidance (if llm_guided)
    llm_prompt TEXT,
    llm_response TEXT,
    llm_model_used TEXT,

    -- Sandbox testing
    sandbox_id TEXT,                         -- Docker container ID
    sandbox_tests_run INTEGER,
    sandbox_tests_passed INTEGER,
    sandbox_runtime_ms INTEGER,
    sandbox_memory_mb INTEGER,
    sandbox_logs TEXT,

    -- Security checks
    static_analysis_passed BOOLEAN,
    no_dangerous_calls BOOLEAN,              -- No eval, exec, os.system with user input
    no_network_in_sandbox BOOLEAN,           -- Network disabled during test
    code_signed BOOLEAN,

    -- State
    status TEXT DEFAULT 'proposed' CHECK (status IN (
        'proposed', 'sandbox_testing', 'sandbox_passed', 'sandbox_failed',
        'approved', 'rejected', 'deployed', 'rolled_back'
    )),
    rejection_reason TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    sandbox_started_at TIMESTAMPTZ,
    sandbox_completed_at TIMESTAMPTZ,
    deployed_at TIMESTAMPTZ
);

-- ============================================================================
-- BENCHMARKS TABLE
-- Define and track benchmark test suites
-- ============================================================================

CREATE TABLE benchmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    category TEXT NOT NULL,                  -- 'success_rate', 'generalization', 'efficiency'

    -- Test cases
    test_cases JSONB NOT NULL,               -- Array of {input, expected_output, criteria}
    test_count INTEGER NOT NULL,

    -- Weights
    weight_in_overall_score FLOAT DEFAULT 1.0,

    -- Metadata
    difficulty TEXT CHECK (difficulty IN ('easy', 'medium', 'hard', 'expert')),
    domain TEXT,

    -- Version control
    version TEXT NOT NULL,
    previous_version_id UUID REFERENCES benchmarks(id),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- BENCHMARK RESULTS TABLE
-- ============================================================================

CREATE TABLE benchmark_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    benchmark_id UUID NOT NULL REFERENCES benchmarks(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,

    -- Results
    score FLOAT NOT NULL,                    -- 0-1
    tests_passed INTEGER NOT NULL,
    tests_failed INTEGER NOT NULL,
    tests_skipped INTEGER DEFAULT 0,

    -- Details
    per_test_results JSONB NOT NULL,         -- {test_id: {passed, output, expected, time_ms}}

    -- Timing
    total_time_ms INTEGER,
    avg_time_per_test_ms FLOAT,

    -- Context
    agent_version TEXT,
    agent_code_hash TEXT,

    -- Timestamps
    run_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(benchmark_id, agent_id, run_at)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Agents
CREATE INDEX idx_agents_name ON agents(name);
CREATE INDEX idx_agents_type ON agents(type);
CREATE INDEX idx_agents_status ON agents(status) WHERE retired_at IS NULL;
CREATE INDEX idx_agents_success_rate ON agents(success_rate DESC);
CREATE INDEX idx_agents_parent ON agents(parent_version_id);

-- Executions
CREATE INDEX idx_executions_agent ON executions(agent_id);
CREATE INDEX idx_executions_task_type ON executions(task_type);
CREATE INDEX idx_executions_success ON executions(success);
CREATE INDEX idx_executions_started ON executions(started_at DESC);
CREATE INDEX idx_executions_fts ON executions USING GIN(task_fts);
CREATE INDEX idx_executions_parent ON executions(parent_execution_id);
CREATE INDEX idx_executions_root ON executions(root_execution_id);

-- Skills
CREATE INDEX idx_skills_category ON skills(category);
CREATE INDEX idx_skills_status ON skills(status) WHERE status = 'active';
CREATE INDEX idx_skills_embedding ON skills USING hnsw(embedding vector_cosine_ops);
CREATE INDEX idx_skills_usage ON skills(usage_count DESC);
CREATE INDEX idx_skills_success ON skills(success_rate DESC);
CREATE INDEX idx_skills_tags ON skills USING GIN(tags);

-- Episodic Memory
CREATE INDEX idx_episodic_execution ON episodic_memory(execution_id);
CREATE INDEX idx_episodic_embedding ON episodic_memory USING hnsw(embedding vector_cosine_ops);
CREATE INDEX idx_episodic_timestamp ON episodic_memory(timestamp DESC);
CREATE INDEX idx_episodic_type ON episodic_memory(event_type);
CREATE INDEX idx_episodic_importance ON episodic_memory(importance_score DESC);

-- Semantic Memory
CREATE INDEX idx_semantic_embedding ON semantic_memory USING hnsw(embedding vector_cosine_ops);
CREATE INDEX idx_semantic_type ON semantic_memory(fact_type);
CREATE INDEX idx_semantic_confidence ON semantic_memory(confidence DESC) WHERE deleted_at IS NULL;
CREATE INDEX idx_semantic_category ON semantic_memory(category);
CREATE INDEX idx_semantic_tags ON semantic_memory USING GIN(tags);

-- Experiments
CREATE INDEX idx_experiments_agent ON improvement_experiments(agent_id);
CREATE INDEX idx_experiments_status ON improvement_experiments(status);
CREATE INDEX idx_experiments_type ON improvement_experiments(improvement_type);

-- Feedback
CREATE INDEX idx_feedback_execution ON feedback(execution_id);
CREATE INDEX idx_feedback_source ON feedback(source);
CREATE INDEX idx_feedback_type ON feedback(rating_type);

-- DSPy
CREATE INDEX idx_dspy_agent ON dspy_optimizations(agent_id);
CREATE INDEX idx_dspy_status ON dspy_optimizations(status);

-- Code Evolution
CREATE INDEX idx_evolution_agent ON code_evolutions(agent_id);
CREATE INDEX idx_evolution_status ON code_evolutions(status);

-- Benchmarks
CREATE INDEX idx_benchmark_results_agent ON benchmark_results(agent_id);
CREATE INDEX idx_benchmark_results_benchmark ON benchmark_results(benchmark_id);
CREATE INDEX idx_benchmark_results_score ON benchmark_results(score DESC);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER agents_updated_at BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER skills_updated_at BEFORE UPDATE ON skills
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER semantic_memory_updated_at BEFORE UPDATE ON semantic_memory
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER benchmarks_updated_at BEFORE UPDATE ON benchmarks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Update agent stats on execution complete
CREATE OR REPLACE FUNCTION update_agent_stats()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.completed_at IS NOT NULL AND OLD.completed_at IS NULL THEN
        UPDATE agents SET
            total_executions = total_executions + 1,
            successful_executions = successful_executions + (CASE WHEN NEW.success THEN 1 ELSE 0 END),
            avg_execution_time_ms = (avg_execution_time_ms * total_executions + COALESCE(NEW.execution_time_ms, 0)) / (total_executions + 1),
            avg_tokens_used = (avg_tokens_used * total_executions + COALESCE(NEW.tokens_total, 0)) / (total_executions + 1),
            last_execution = NEW.completed_at
        WHERE id = NEW.agent_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER executions_update_agent_stats
    AFTER UPDATE ON executions
    FOR EACH ROW EXECUTE FUNCTION update_agent_stats();

-- Update skill usage stats
CREATE OR REPLACE FUNCTION update_skill_usage()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.skills_used IS NOT NULL AND array_length(NEW.skills_used, 1) > 0 THEN
        UPDATE skills SET
            usage_count = usage_count + 1,
            last_used = NOW(),
            last_success = CASE WHEN NEW.success THEN NOW() ELSE last_success END,
            last_failure = CASE WHEN NOT NEW.success THEN NOW() ELSE last_failure END,
            failure_count = failure_count + CASE WHEN NOT NEW.success THEN 1 ELSE 0 END
        WHERE id = ANY(NEW.skills_used);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER executions_update_skill_usage
    AFTER INSERT ON executions
    FOR EACH ROW EXECUTE FUNCTION update_skill_usage();

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert a baseline decomposer agent as seed data
INSERT INTO agents (
    name,
    version,
    description,
    type,
    code_module,
    code_hash,
    original_code,
    system_prompt,
    task_prompt_template,
    is_baseline
) VALUES (
    'decomposer',
    '1.0.0',
    'Task decomposition agent - breaks complex tasks into subtasks',
    'single',
    'sia.agents.decomposer',
    'seed_hash_placeholder',
    '# Placeholder - will be replaced with actual code',
    'You are an expert task decomposition agent. Your job is to break down complex tasks into clear, actionable subtasks that can be executed independently or in sequence.',
    'Break down the following task into subtasks:\n\nTask: {{task}}\n\nProvide a structured list of subtasks with dependencies noted.',
    true
);

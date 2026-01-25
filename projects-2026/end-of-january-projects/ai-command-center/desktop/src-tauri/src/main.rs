// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::process::Command;
use std::sync::Arc;
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, Runtime,
};
use tokio::sync::Mutex;

// App state for tracking running services
pub struct AppState {
    pub router_pid: Arc<Mutex<Option<u32>>>,
    pub litellm_pid: Arc<Mutex<Option<u32>>>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            router_pid: Arc::new(Mutex::new(None)),
            litellm_pid: Arc::new(Mutex::new(None)),
        }
    }
}

// Health check response
#[derive(Serialize, Deserialize, Clone)]
pub struct HealthStatus {
    pub service: String,
    pub healthy: bool,
    pub message: String,
    pub latency_ms: Option<u64>,
}

// All health response
#[derive(Serialize, Deserialize)]
pub struct AllHealthResponse {
    pub router: HealthStatus,
    pub litellm: HealthStatus,
    pub ollama: HealthStatus,
    pub redis: HealthStatus,
    pub langfuse: HealthStatus,
}

// Config structures
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct ModelConfig {
    pub model_name: String,
    pub litellm_params: LiteLLMParams,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct LiteLLMParams {
    pub model: String,
    pub api_base: String,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct Config {
    pub model_list: Vec<ModelConfig>,
    #[serde(default)]
    pub litellm_settings: serde_yaml::Value,
    #[serde(default)]
    pub router_settings: serde_yaml::Value,
    #[serde(default)]
    pub general_settings: serde_yaml::Value,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct RoutingPolicy {
    #[serde(default)]
    pub version: String,
    #[serde(default)]
    pub privacy: PrivacyPolicy,
    #[serde(default)]
    pub complexity: ComplexityPolicy,
    #[serde(default)]
    pub injection: InjectionPolicy,
    #[serde(default)]
    pub routing: serde_yaml::Value,
}

#[derive(Serialize, Deserialize, Debug, Default)]
pub struct PrivacyPolicy {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default)]
    pub pii_regexes: Vec<String>,
    #[serde(default)]
    pub entropy_threshold: f64,
    #[serde(default)]
    pub min_token_length: u32,
    #[serde(default)]
    pub sensitive_model: String,
}

#[derive(Serialize, Deserialize, Debug, Default)]
pub struct ComplexityPolicy {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default)]
    pub simple_max_tokens: u32,
    #[serde(default)]
    pub medium_max_tokens: u32,
    #[serde(default)]
    pub code_signals: Vec<String>,
    #[serde(default)]
    pub reasoning_signals: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Default)]
pub struct InjectionPolicy {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default)]
    pub patterns: Vec<String>,
    #[serde(default)]
    pub block_on_injection: bool,
}

#[derive(Serialize, Deserialize)]
pub struct ValidationResult {
    pub valid: bool,
    pub errors: Vec<String>,
    pub warnings: Vec<String>,
}

fn get_config_dir() -> Result<std::path::PathBuf, String> {
    dirs::home_dir()
        .map(|h| h.join(".config/ai-command-center"))
        .ok_or_else(|| "Could not find home directory".to_string())
}

// Service management commands - DISABLED per architecture mandate
// Services are managed by LaunchAgents, not the desktop app.
// These commands are kept as no-ops to maintain API compatibility.

#[tauri::command]
async fn start_router(_state: tauri::State<'_, AppState>) -> Result<String, String> {
    Err("Service management disabled. Services are managed by LaunchAgents. Run: launchctl start com.aicommandcenter.router".to_string())
}

#[tauri::command]
async fn stop_router(_state: tauri::State<'_, AppState>) -> Result<String, String> {
    Err("Service management disabled. Services are managed by LaunchAgents. Run: launchctl stop com.aicommandcenter.router".to_string())
}

#[tauri::command]
async fn start_litellm(_state: tauri::State<'_, AppState>) -> Result<String, String> {
    Err("Service management disabled. Services are managed by LaunchAgents. Run: launchctl start com.aicommandcenter.litellm".to_string())
}

#[tauri::command]
async fn stop_litellm(_state: tauri::State<'_, AppState>) -> Result<String, String> {
    Err("Service management disabled. Services are managed by LaunchAgents. Run: launchctl stop com.aicommandcenter.litellm".to_string())
}

#[tauri::command]
async fn start_all(_state: tauri::State<'_, AppState>) -> Result<String, String> {
    Err("Service management disabled. Services are managed by LaunchAgents.".to_string())
}

#[tauri::command]
async fn stop_all(_state: tauri::State<'_, AppState>) -> Result<String, String> {
    Err("Service management disabled. Services are managed by LaunchAgents.".to_string())
}

// Health check commands
async fn check_http_health(url: &str, service: &str) -> HealthStatus {
    let start = std::time::Instant::now();
    let client = match reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(5))
        .build()
    {
        Ok(c) => c,
        Err(e) => {
            return HealthStatus {
                service: service.to_string(),
                healthy: false,
                message: format!("Failed to create HTTP client: {}", e),
                latency_ms: None,
            };
        }
    };

    match client.get(url).send().await {
        Ok(resp) => {
            let latency = start.elapsed().as_millis() as u64;
            if resp.status().is_success() {
                HealthStatus {
                    service: service.to_string(),
                    healthy: true,
                    message: "OK".to_string(),
                    latency_ms: Some(latency),
                }
            } else {
                HealthStatus {
                    service: service.to_string(),
                    healthy: false,
                    message: format!("Status: {}", resp.status()),
                    latency_ms: Some(latency),
                }
            }
        }
        Err(e) => HealthStatus {
            service: service.to_string(),
            healthy: false,
            message: format!("Connection failed: {}", e),
            latency_ms: None,
        },
    }
}

#[tauri::command]
async fn check_router_health() -> HealthStatus {
    check_http_health("http://localhost:4000/health", "Smart Router").await
}

#[tauri::command]
async fn check_litellm_health() -> HealthStatus {
    check_http_health("http://localhost:4001/health", "LiteLLM").await
}

#[tauri::command]
async fn check_ollama_health() -> HealthStatus {
    check_http_health("http://localhost:11434/api/tags", "Ollama").await
}

#[tauri::command]
async fn check_redis_health() -> HealthStatus {
    let output = Command::new("redis-cli").args(["ping"]).output();

    match output {
        Ok(out) => {
            let stdout = String::from_utf8_lossy(&out.stdout);
            if stdout.trim() == "PONG" {
                HealthStatus {
                    service: "Redis".to_string(),
                    healthy: true,
                    message: "PONG".to_string(),
                    latency_ms: None,
                }
            } else {
                HealthStatus {
                    service: "Redis".to_string(),
                    healthy: false,
                    message: format!("Unexpected response: {}", stdout.trim()),
                    latency_ms: None,
                }
            }
        }
        Err(e) => HealthStatus {
            service: "Redis".to_string(),
            healthy: false,
            message: format!("Error: {}", e),
            latency_ms: None,
        },
    }
}

#[tauri::command]
async fn check_langfuse_health() -> HealthStatus {
    check_http_health("http://localhost:3001/api/public/health", "Langfuse").await
}

#[tauri::command]
async fn get_all_health() -> AllHealthResponse {
    let (router, litellm, ollama, redis, langfuse) = tokio::join!(
        check_router_health(),
        check_litellm_health(),
        check_ollama_health(),
        check_redis_health(),
        check_langfuse_health(),
    );

    AllHealthResponse {
        router,
        litellm,
        ollama,
        redis,
        langfuse,
    }
}

// Config commands
#[tauri::command]
async fn read_config() -> Result<Config, String> {
    let config_path = get_config_dir()?.join("config.yaml");
    let content = std::fs::read_to_string(&config_path)
        .map_err(|e| format!("Failed to read config: {}", e))?;
    serde_yaml::from_str(&content).map_err(|e| format!("Failed to parse config: {}", e))
}

#[tauri::command]
async fn write_config(config: Config) -> Result<String, String> {
    let config_path = get_config_dir()?.join("config.yaml");
    let content =
        serde_yaml::to_string(&config).map_err(|e| format!("Failed to serialize config: {}", e))?;
    std::fs::write(&config_path, content)
        .map_err(|e| format!("Failed to write config: {}", e))?;
    Ok("Config saved successfully".to_string())
}

#[tauri::command]
async fn read_policy() -> Result<RoutingPolicy, String> {
    let policy_path = get_config_dir()?.join("routing/policy.yaml");
    let content = std::fs::read_to_string(&policy_path)
        .map_err(|e| format!("Failed to read policy: {}", e))?;
    serde_yaml::from_str(&content).map_err(|e| format!("Failed to parse policy: {}", e))
}

#[tauri::command]
async fn write_policy(policy: RoutingPolicy) -> Result<String, String> {
    let policy_path = get_config_dir()?.join("routing/policy.yaml");
    let content =
        serde_yaml::to_string(&policy).map_err(|e| format!("Failed to serialize policy: {}", e))?;
    std::fs::write(&policy_path, content)
        .map_err(|e| format!("Failed to write policy: {}", e))?;
    Ok("Policy saved successfully".to_string())
}

#[tauri::command]
async fn validate_config(config: Config) -> ValidationResult {
    let mut errors = Vec::new();
    let mut warnings = Vec::new();

    // Validate models
    if config.model_list.is_empty() {
        errors.push("At least one model must be configured".to_string());
    }

    for model in &config.model_list {
        if model.model_name.is_empty() {
            errors.push("Model name cannot be empty".to_string());
        }
        if !model.litellm_params.api_base.starts_with("http") {
            errors.push(format!(
                "Invalid api_base for {}: must start with http(s)",
                model.model_name
            ));
        }
    }

    // Check for recommended models
    let model_names: Vec<&str> = config
        .model_list
        .iter()
        .map(|m| m.model_name.as_str())
        .collect();
    if !model_names.contains(&"llama-fast") {
        warnings.push("Recommended: Add 'llama-fast' model for quick responses".to_string());
    }

    ValidationResult {
        valid: errors.is_empty(),
        errors,
        warnings,
    }
}

// Ollama commands
#[derive(Serialize, Deserialize)]
pub struct OllamaModel {
    pub name: String,
    pub size: String,
    pub modified: String,
}

#[tauri::command]
async fn list_ollama_models() -> Result<Vec<OllamaModel>, String> {
    let output = Command::new("ollama")
        .args(["list"])
        .output()
        .map_err(|e| format!("Failed to run ollama list: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout);

    let models: Vec<OllamaModel> = stdout
        .lines()
        .skip(1) // Skip header
        .filter(|line| !line.is_empty())
        .filter_map(|line| {
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 4 {
                Some(OllamaModel {
                    name: parts[0].to_string(),
                    size: parts[2].to_string(),
                    modified: parts[3..].join(" "),
                })
            } else {
                None
            }
        })
        .collect();

    Ok(models)
}

#[tauri::command]
async fn pull_ollama_model(model_name: String) -> Result<String, String> {
    let output = Command::new("ollama")
        .args(["pull", &model_name])
        .output()
        .map_err(|e| format!("Failed to pull model: {}", e))?;

    if output.status.success() {
        Ok(format!("Successfully pulled {}", model_name))
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

#[tauri::command]
async fn delete_ollama_model(model_name: String) -> Result<String, String> {
    let output = Command::new("ollama")
        .args(["rm", &model_name])
        .output()
        .map_err(|e| format!("Failed to delete model: {}", e))?;

    if output.status.success() {
        Ok(format!("Deleted {}", model_name))
    } else {
        Err(String::from_utf8_lossy(&output.stderr).to_string())
    }
}

// Log reading - optimized tail-only implementation
#[tauri::command]
async fn read_log_tail(service: String, lines: usize) -> Result<Vec<String>, String> {
    use std::io::{BufRead, BufReader, Seek, SeekFrom};

    let config_dir = get_config_dir()?;
    let filename = match service.as_str() {
        "router" => "router.out.log",
        "litellm" => "litellm.out.log",
        _ => return Err(format!("Unknown service: {}", service)),
    };

    let log_path = config_dir.join("logs").join(filename);

    if !log_path.exists() {
        return Ok(vec![format!("Log file not found: {:?}", log_path)]);
    }

    // Tail-only read: read from end of file to avoid loading entire file
    let file = std::fs::File::open(&log_path)
        .map_err(|e| format!("Failed to open log: {}", e))?;

    let metadata = file.metadata()
        .map_err(|e| format!("Failed to get file metadata: {}", e))?;

    let file_size = metadata.len();

    // For small files (< 64KB), just read the whole thing
    if file_size < 65536 {
        let reader = BufReader::new(file);
        let all_lines: Vec<String> = reader.lines()
            .filter_map(|l| l.ok())
            .collect();
        let start = all_lines.len().saturating_sub(lines);
        return Ok(all_lines[start..].to_vec());
    }

    // For larger files, read last ~64KB and extract lines
    let mut file = file;
    let seek_pos = file_size.saturating_sub(65536);
    file.seek(SeekFrom::Start(seek_pos))
        .map_err(|e| format!("Failed to seek: {}", e))?;

    let reader = BufReader::new(file);
    let mut all_lines: Vec<String> = reader.lines()
        .filter_map(|l| l.ok())
        .collect();

    // If we seeked into the middle of a line, discard the first partial line
    if seek_pos > 0 && !all_lines.is_empty() {
        all_lines.remove(0);
    }

    let start = all_lines.len().saturating_sub(lines);
    Ok(all_lines[start..].to_vec())
}

// Test commands
#[derive(Serialize, Deserialize)]
pub struct TestResult {
    pub service: String,
    pub success: bool,
    pub message: String,
    pub latency_ms: Option<u64>,
}

#[derive(Serialize, Deserialize)]
pub struct ChatTestResult {
    pub success: bool,
    pub model: String,
    pub response_preview: String,
    pub latency_ms: u64,
    pub routing_info: Option<RoutingInfo>,
    pub error: Option<String>,
}

#[derive(Serialize, Deserialize)]
pub struct RoutingInfo {
    pub is_sensitive: bool,
    pub complexity: String,
    pub routed_model: String,
}

#[tauri::command]
async fn test_service_connection(service: String) -> TestResult {
    let url = match service.as_str() {
        "router" => "http://localhost:4000/health",
        "litellm" => "http://localhost:4001/health",
        "ollama" => "http://localhost:11434/api/tags",
        "redis" => {
            // Test Redis via command
            let output = std::process::Command::new("redis-cli")
                .args(["ping"])
                .output();
            return match output {
                Ok(out) => {
                    let stdout = String::from_utf8_lossy(&out.stdout);
                    TestResult {
                        service,
                        success: stdout.trim() == "PONG",
                        message: if stdout.trim() == "PONG" {
                            "Connected".to_string()
                        } else {
                            stdout.to_string()
                        },
                        latency_ms: None,
                    }
                }
                Err(e) => TestResult {
                    service,
                    success: false,
                    message: format!("Error: {}", e),
                    latency_ms: None,
                },
            };
        }
        "langfuse" => "http://localhost:3001/api/public/health",
        _ => {
            return TestResult {
                service,
                success: false,
                message: "Unknown service".to_string(),
                latency_ms: None,
            }
        }
    };

    let client = reqwest::Client::new();
    let start = std::time::Instant::now();

    match client.get(url).timeout(std::time::Duration::from_secs(5)).send().await {
        Ok(resp) => {
            let latency = start.elapsed().as_millis() as u64;
            TestResult {
                service,
                success: resp.status().is_success(),
                message: if resp.status().is_success() {
                    "Connected".to_string()
                } else {
                    format!("Status: {}", resp.status())
                },
                latency_ms: Some(latency),
            }
        }
        Err(e) => TestResult {
            service,
            success: false,
            message: format!("Error: {}", e),
            latency_ms: None,
        },
    }
}

#[tauri::command]
async fn test_chat_completion(prompt: String, model: String) -> ChatTestResult {
    let client = reqwest::Client::new();
    let start = std::time::Instant::now();

    let request_body = serde_json::json!({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 50
    });

    match client
        .post("http://localhost:4000/v1/chat/completions")
        .header("Authorization", "Bearer sk-command-center-local")
        .header("Content-Type", "application/json")
        .json(&request_body)
        .timeout(std::time::Duration::from_secs(60))
        .send()
        .await
    {
        Ok(resp) => {
            let latency = start.elapsed().as_millis() as u64;
            if resp.status().is_success() {
                match resp.json::<serde_json::Value>().await {
                    Ok(data) => {
                        let response_text = data["choices"][0]["message"]["content"]
                            .as_str()
                            .unwrap_or("")
                            .chars()
                            .take(100)
                            .collect::<String>();

                        let routing_info = data.get("_routing").map(|r| RoutingInfo {
                            is_sensitive: r["is_sensitive"].as_bool().unwrap_or(false),
                            complexity: r["complexity"].as_str().unwrap_or("unknown").to_string(),
                            routed_model: r["routed_model"].as_str().unwrap_or(&model).to_string(),
                        });

                        ChatTestResult {
                            success: true,
                            model,
                            response_preview: response_text,
                            latency_ms: latency,
                            routing_info,
                            error: None,
                        }
                    }
                    Err(e) => ChatTestResult {
                        success: false,
                        model,
                        response_preview: String::new(),
                        latency_ms: latency,
                        routing_info: None,
                        error: Some(format!("Parse error: {}", e)),
                    },
                }
            } else {
                ChatTestResult {
                    success: false,
                    model,
                    response_preview: String::new(),
                    latency_ms: latency,
                    routing_info: None,
                    error: Some(format!("Status: {}", resp.status())),
                }
            }
        }
        Err(e) => ChatTestResult {
            success: false,
            model,
            response_preview: String::new(),
            latency_ms: start.elapsed().as_millis() as u64,
            routing_info: None,
            error: Some(format!("Error: {}", e)),
        },
    }
}

// Setup system tray - Read-only mode (service management disabled)
fn setup_tray<R: Runtime>(app: &AppHandle<R>) -> Result<(), Box<dyn std::error::Error>> {
    let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let show_item = MenuItem::with_id(app, "show", "Show Window", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[&show_item, &quit_item])?;

    let icon = app.default_window_icon()
        .ok_or("No default window icon configured")?
        .clone();

    let _tray = TrayIconBuilder::new()
        .icon(icon)
        .menu(&menu)
        .on_menu_event(move |app, event| match event.id.as_ref() {
            "quit" => {
                app.exit(0);
            }
            "show" => {
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                let app = tray.app_handle();
                if let Some(window) = app.get_webview_window("main") {
                    let _ = window.show();
                    let _ = window.set_focus();
                }
            }
        })
        .build(app)?;

    Ok(())
}

fn main() {
    env_logger::init();

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_notification::init())
        // Removed shell and fs plugins per security audit
        .manage(AppState::default())
        .setup(|app| {
            setup_tray(app.handle())?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                // Hide window instead of closing
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .invoke_handler(tauri::generate_handler![
            start_router,
            stop_router,
            start_litellm,
            stop_litellm,
            start_all,
            stop_all,
            check_router_health,
            check_litellm_health,
            check_ollama_health,
            check_redis_health,
            check_langfuse_health,
            get_all_health,
            read_config,
            write_config,
            read_policy,
            write_policy,
            validate_config,
            list_ollama_models,
            pull_ollama_model,
            delete_ollama_model,
            read_log_tail,
            test_service_connection,
            test_chat_completion,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_config_dir() {
        let result = get_config_dir();
        assert!(result.is_ok());
        let path = result.unwrap();
        assert!(path.ends_with(".config/ai-command-center"));
    }

    #[test]
    fn test_validation_empty_model_list() {
        let config = Config {
            model_list: vec![],
            litellm_settings: serde_yaml::Value::Null,
            router_settings: serde_yaml::Value::Null,
            general_settings: serde_yaml::Value::Null,
        };

        let rt = tokio::runtime::Runtime::new().unwrap();
        let result = rt.block_on(validate_config(config));

        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.contains("At least one model")));
    }

    #[test]
    fn test_validation_empty_model_name() {
        let config = Config {
            model_list: vec![ModelConfig {
                model_name: "".to_string(),
                litellm_params: LiteLLMParams {
                    model: "ollama/test".to_string(),
                    api_base: "http://localhost:11434".to_string(),
                },
            }],
            litellm_settings: serde_yaml::Value::Null,
            router_settings: serde_yaml::Value::Null,
            general_settings: serde_yaml::Value::Null,
        };

        let rt = tokio::runtime::Runtime::new().unwrap();
        let result = rt.block_on(validate_config(config));

        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.contains("name cannot be empty")));
    }

    #[test]
    fn test_validation_invalid_api_base() {
        let config = Config {
            model_list: vec![ModelConfig {
                model_name: "test-model".to_string(),
                litellm_params: LiteLLMParams {
                    model: "ollama/test".to_string(),
                    api_base: "invalid-url".to_string(),
                },
            }],
            litellm_settings: serde_yaml::Value::Null,
            router_settings: serde_yaml::Value::Null,
            general_settings: serde_yaml::Value::Null,
        };

        let rt = tokio::runtime::Runtime::new().unwrap();
        let result = rt.block_on(validate_config(config));

        assert!(!result.valid);
        assert!(result.errors.iter().any(|e| e.contains("Invalid api_base")));
    }

    #[test]
    fn test_validation_valid_config() {
        let config = Config {
            model_list: vec![
                ModelConfig {
                    model_name: "llama-fast".to_string(),
                    litellm_params: LiteLLMParams {
                        model: "ollama/llama3.2".to_string(),
                        api_base: "http://localhost:11434".to_string(),
                    },
                },
            ],
            litellm_settings: serde_yaml::Value::Null,
            router_settings: serde_yaml::Value::Null,
            general_settings: serde_yaml::Value::Null,
        };

        let rt = tokio::runtime::Runtime::new().unwrap();
        let result = rt.block_on(validate_config(config));

        assert!(result.valid);
        assert!(result.errors.is_empty());
    }

    #[test]
    fn test_validation_warns_missing_llama_fast() {
        let config = Config {
            model_list: vec![ModelConfig {
                model_name: "qwen-local".to_string(),
                litellm_params: LiteLLMParams {
                    model: "ollama/qwen2.5".to_string(),
                    api_base: "http://localhost:11434".to_string(),
                },
            }],
            litellm_settings: serde_yaml::Value::Null,
            router_settings: serde_yaml::Value::Null,
            general_settings: serde_yaml::Value::Null,
        };

        let rt = tokio::runtime::Runtime::new().unwrap();
        let result = rt.block_on(validate_config(config));

        assert!(result.valid); // Valid but with warning
        assert!(result.warnings.iter().any(|w| w.contains("llama-fast")));
    }

    #[test]
    fn test_health_status_serialization() {
        let status = HealthStatus {
            service: "test".to_string(),
            healthy: true,
            message: "OK".to_string(),
            latency_ms: Some(42),
        };

        let json = serde_json::to_string(&status).unwrap();
        assert!(json.contains("\"healthy\":true"));
        assert!(json.contains("\"latency_ms\":42"));
    }

    #[test]
    fn test_routing_policy_default() {
        let policy: RoutingPolicy = serde_yaml::from_str("{}").unwrap();
        assert!(!policy.privacy.enabled);
        assert!(!policy.complexity.enabled);
        assert!(!policy.injection.enabled);
    }
}

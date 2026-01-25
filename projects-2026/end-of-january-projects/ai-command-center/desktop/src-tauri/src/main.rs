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

// Service management commands
#[tauri::command]
async fn start_router(state: tauri::State<'_, AppState>) -> Result<String, String> {
    let mut pid_guard = state.router_pid.lock().await;
    if pid_guard.is_some() {
        return Err("Router already running".to_string());
    }

    let config_dir = get_config_dir()?;
    let start_script = config_dir.join("start_router.sh");

    if !start_script.exists() {
        return Err(format!("Start script not found: {:?}", start_script));
    }

    let child = Command::new("bash")
        .arg(start_script.to_str().unwrap())
        .current_dir(&config_dir)
        .spawn()
        .map_err(|e| format!("Failed to start router: {}", e))?;

    let pid = child.id();
    *pid_guard = Some(pid);

    Ok(format!("Router started with PID {}", pid))
}

#[tauri::command]
async fn stop_router(state: tauri::State<'_, AppState>) -> Result<String, String> {
    let mut pid_guard = state.router_pid.lock().await;

    // Try to kill by port (more reliable than PID for spawned scripts)
    let output = Command::new("bash")
        .args(["-c", "lsof -ti:4000 | xargs kill -9 2>/dev/null || true"])
        .output()
        .map_err(|e| format!("Failed to stop router: {}", e))?;

    *pid_guard = None;

    if output.status.success() {
        Ok("Router stopped".to_string())
    } else {
        Ok("Router was not running".to_string())
    }
}

#[tauri::command]
async fn start_litellm(state: tauri::State<'_, AppState>) -> Result<String, String> {
    let mut pid_guard = state.litellm_pid.lock().await;
    if pid_guard.is_some() {
        return Err("LiteLLM already running".to_string());
    }

    let config_dir = get_config_dir()?;
    let start_script = config_dir.join("start_litellm.sh");

    if !start_script.exists() {
        return Err(format!("Start script not found: {:?}", start_script));
    }

    let child = Command::new("bash")
        .arg(start_script.to_str().unwrap())
        .current_dir(&config_dir)
        .spawn()
        .map_err(|e| format!("Failed to start LiteLLM: {}", e))?;

    let pid = child.id();
    *pid_guard = Some(pid);

    Ok(format!("LiteLLM started with PID {}", pid))
}

#[tauri::command]
async fn stop_litellm(state: tauri::State<'_, AppState>) -> Result<String, String> {
    let mut pid_guard = state.litellm_pid.lock().await;

    // Try to kill by port
    let output = Command::new("bash")
        .args(["-c", "lsof -ti:4001 | xargs kill -9 2>/dev/null || true"])
        .output()
        .map_err(|e| format!("Failed to stop LiteLLM: {}", e))?;

    *pid_guard = None;

    if output.status.success() {
        Ok("LiteLLM stopped".to_string())
    } else {
        Ok("LiteLLM was not running".to_string())
    }
}

#[tauri::command]
async fn start_all(state: tauri::State<'_, AppState>) -> Result<String, String> {
    let _ = start_litellm(state.clone()).await;
    // Give LiteLLM time to start
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
    let _ = start_router(state).await;
    Ok("All services started".to_string())
}

#[tauri::command]
async fn stop_all(state: tauri::State<'_, AppState>) -> Result<String, String> {
    let _ = stop_router(state.clone()).await;
    let _ = stop_litellm(state).await;
    Ok("All services stopped".to_string())
}

// Health check commands
async fn check_http_health(url: &str, service: &str) -> HealthStatus {
    let start = std::time::Instant::now();
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(5))
        .build()
        .unwrap();

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

// Log reading
#[tauri::command]
async fn read_log_tail(service: String, lines: usize) -> Result<Vec<String>, String> {
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

    let content = std::fs::read_to_string(&log_path)
        .map_err(|e| format!("Failed to read log: {}", e))?;

    let all_lines: Vec<String> = content.lines().map(|s| s.to_string()).collect();
    let start = if all_lines.len() > lines {
        all_lines.len() - lines
    } else {
        0
    };

    Ok(all_lines[start..].to_vec())
}

// Helper functions for tray actions
async fn do_start_all(state: tauri::State<'_, AppState>) -> Result<String, String> {
    let _ = start_litellm(state.clone()).await;
    tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
    let _ = start_router(state).await;
    Ok("All services started".to_string())
}

async fn do_stop_all(state: tauri::State<'_, AppState>) -> Result<String, String> {
    let _ = stop_router(state.clone()).await;
    let _ = stop_litellm(state).await;
    Ok("All services stopped".to_string())
}

// Setup system tray
fn setup_tray<R: Runtime>(app: &AppHandle<R>) -> Result<(), Box<dyn std::error::Error>> {
    let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let show_item = MenuItem::with_id(app, "show", "Show Window", true, None::<&str>)?;
    let start_item = MenuItem::with_id(app, "start_all_svc", "Start All Services", true, None::<&str>)?;
    let stop_item = MenuItem::with_id(app, "stop_all_svc", "Stop All Services", true, None::<&str>)?;

    let menu = Menu::with_items(app, &[&show_item, &start_item, &stop_item, &quit_item])?;

    let _tray = TrayIconBuilder::new()
        .icon(app.default_window_icon().unwrap().clone())
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
            "start_all_svc" => {
                let app_handle = app.clone();
                tauri::async_runtime::spawn(async move {
                    let state = app_handle.state::<AppState>();
                    let _ = do_start_all(state).await;
                });
            }
            "stop_all_svc" => {
                let app_handle = app.clone();
                tauri::async_runtime::spawn(async move {
                    let state = app_handle.state::<AppState>();
                    let _ = do_stop_all(state).await;
                });
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
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_fs::init())
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
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

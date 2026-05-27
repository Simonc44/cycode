#![allow(
    dead_code,
    unused_imports,
    unused_variables,
    clippy::unneeded_struct_pattern,
    clippy::unnecessary_wraps,
    clippy::unused_self
)]
mod init;
mod input;
mod render;

use std::collections::BTreeSet;
use std::env;
use std::fs;
use std::io::{self, Read, Write};
use std::net::TcpListener;
use std::ops::{Deref, DerefMut};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::mpsc::{self, Receiver, RecvTimeoutError, Sender};
use std::sync::{Arc, Mutex};
use std::thread::{self, JoinHandle};
use std::time::{Duration, Instant, UNIX_EPOCH};

use api::{
    resolve_startup_auth_source, CygnisClient, AuthSource, ContentBlockDelta, InputContentBlock,
    InputMessage, MessageRequest, MessageResponse, OutputContentBlock, PromptCache,
    StreamEvent as ApiStreamEvent, ToolChoice, ToolDefinition, ToolResultContentBlock,
    MessageStream as ApiMessageStream, ApiError,
};

use commands::{
    handle_agents_slash_command, handle_mcp_slash_command, handle_skills_slash_command,
    render_slash_command_help, resume_supported_slash_commands,
    slash_command_specs, SlashCommand,
};
use compat_harness::{extract_manifest, UpstreamPaths};
use init::initialize_repo;
use plugins::{PluginHooks, PluginManager, PluginManagerConfig, PluginRegistry};
use render::{MarkdownStreamState, Spinner, TerminalRenderer};
use runtime::{
    clear_oauth_credentials, format_usd, generate_pkce_pair, generate_state, load_system_prompt,
    parse_oauth_callback_request_target, pricing_for_model, resolve_sandbox_status,
    save_oauth_credentials, ApiClient, ApiRequest, AssistantEvent, CompactionConfig, ConfigLoader,
    ConfigSource, ContentBlock, ConversationMessage, ConversationRuntime, McpServerManager,
    McpTool, MessageRole, ModelPricing, OAuthAuthorizationRequest, OAuthConfig,
    OAuthTokenExchangeRequest, PermissionMode, PermissionPolicy, ProjectContext, PromptCacheEvent,
    ResolvedPermissionMode, RuntimeError, Session, TokenUsage, ToolError, ToolExecutor,
    UsageTracker,
};
use serde::{Deserialize, Serialize};
use serde_json::json;
use tools::{GlobalToolRegistry, RuntimeToolDefinition, ToolSearchOutput};
use indicatif::{ProgressBar, ProgressStyle};
use walkdir::WalkDir;
use colored::*;

// --- CYGNIS V2.5 PRESTIGE CONSTANTS ---
const VERSION: &str = "2.5.0";
const DEFAULT_MODEL: &str = "claude-3-5-sonnet-20241022";

// --- SYSTEM UTILS ---

fn ensure_environment() {
    if env::var("HOME").is_err() {
        if let Ok(profile) = env::var("USERPROFILE") {
            env::set_var("HOME", &profile);
        }
    }
    let _ = fs::read_to_string(".env").map(|content| {
        for line in content.lines() {
            if let Some((k, v)) = line.split_once('=') {
                env::set_var(k.trim(), v.trim());
            }
        }
    });
}

fn save_config(key: &str, value: &str) -> io::Result<()> {
    let mut config = std::collections::HashMap::new();
    if let Ok(content) = fs::read_to_string(".env") {
        for line in content.lines() {
            if let Some((k, v)) = line.split_once('=') {
                config.insert(k.trim().to_string(), v.trim().to_string());
            }
        }
    }
    config.insert(key.to_string(), value.to_string());
    let new_content = config.iter().map(|(k, v)| format!("{k}={v}")).collect::<Vec<_>>().join("\n");
    fs::write(".env", new_content)
}

fn get_project_index() -> String {
    let mut files = Vec::new();
    for entry in WalkDir::new(".").max_depth(3).into_iter().filter_map(|e| e.ok()) {
        if entry.file_type().is_file() {
            let path = entry.path().display().to_string();
            if !path.contains("target") && !path.contains(".git") && !path.contains("node_modules") {
                files.push(path);
            }
        }
    }
    files.join("\n")
}

fn get_git_branch() -> String {
    let output = Command::new("git")
        .args(["rev-parse", "--abbrev-ref", "HEAD"])
        .output();

    match output {
        Ok(o) if o.status.success() => {
            let branch = String::from_utf8_lossy(&o.stdout).trim().to_string();
            if branch.is_empty() { "detached".to_string() } else { branch }
        },
        _ => "no-git".to_string(),
    }
}

fn shorten_path(path: &Path) -> String {
    let path_str = path.to_string_lossy();
    if path_str.len() > 40 {
        let parts: Vec<&str> = path_str.split(|c| c == '/' || c == '\\').collect();
        if parts.len() > 3 {
            return format!(".../{}/{}", parts[parts.len() - 2], parts[parts.len() - 1]);
        }
    }
    path_str.into_owned()
}

// --- VISUAL DASHBOARD ---

fn boot_sequence() {
    println!("{}", "[ SYSTEM ] Initializing Cygnis Core...".bright_black());
    thread::sleep(Duration::from_millis(200));
    println!("{} Loading Claude-3-5-Sonnet...", "[  OK  ]".green());
    thread::sleep(Duration::from_millis(200));
    println!("{} Modules connected.", "[  OK  ]".green());
    thread::sleep(Duration::from_millis(300));
}

fn print_onboarding_screen() {
    let orange = "\x1b[38;5;208m";
    let gray = "\x1b[38;5;242m";
    let reset = "\x1b[0m";
    let bold = "\x1b[1m";

    println!("\n {}Welcome to CYGNIS CODE v{}{}", orange, VERSION, reset);
    println!(" {}………………………………………………………………………………………………………………………………………………………………………………{}", gray, reset);
    println!(r#"
     * {o}█████▓▓░{r}
                                   * {o}███▓░     ░░{r}
             ░░░░░░                          {o}███▓░{r}
     ░░░   ░░░░░░░░░░                        {o}███▓░{r}
    ░░░░░░░░░░░░░░░░░░░    * {o}██▓░░     ▓{r}
                                              {o}░▓▓███▓▓░{r}
 * ░░░░
                                  ░░░░░░░░
                                ░░░░░░░░░░░░░░░░
           ███████
        █████████████
      █████  ███  █████
      █████  ███  █████
        █████████████
           ███████
"#, o = orange, r = reset);
    println!(" {}…………………{}█ █   █ █{}………………………………………………………………………………………………………………{}", gray, orange, gray, reset);
    println!("\n  {}Let's get started.{}", bold, reset);
}

fn print_prestige_dashboard(model: &str) {
    let branch = get_git_branch();
    let cwd = env::current_dir().unwrap_or_default();
    let theme = env::var("CYGNIS_THEME").unwrap_or_else(|_| "Dark".to_string());

    let title = "CYGNIS CODE".truecolor(255, 140, 0).bold();
    let version = format!("v{}", VERSION).bright_black();
    println!("\n{} {}", title, version);
    println!("{}", "░░▒▒▓▓██████████████████████████████████████████████████████████████████▓▓▒▒░░".bright_black());

    // Exact visible character calculation for alignment
    let status_indicator = "● Online";
    let info = format!("Status: {} │ Model: {} │ Theme: {}", status_indicator.green().bold(), model.cyan(), theme.yellow());
    let visible_len = format!("Status: ● Online │ Model: {} │ Theme: {}", model, theme).len();
    let total_box_width: usize = 76;
    let padding = total_box_width.saturating_sub(visible_len);

    println!("{}", "╔════════════════════════════════════════════════════════════════════════════╗".bright_cyan());
    println!("║  {}{}  ║", info, " ".repeat(padding));
    println!("{}", "╚════════════════════════════════════════════════════════════════════════════╝".bright_cyan());

    println!("  {} {}  │  {} {}", "Working Dir:".bright_black(), shorten_path(&cwd).white(), "Branch:".bright_black(), branch.bright_cyan());
    println!("{}\n", "░░▒▒▓▓██████████████████████████████████████████████████████████████████▓▓▒▒░░".bright_black());
}

fn print_diff(path: &str, old: &str, new: &str) {
    println!("\n{} Proposed Changes for {}", "╭──".bright_black(), path.white().bold());
    for line in old.lines().take(3) { println!("{} {}", "│".bright_black(), format!("- {}", line).red()); }
    println!("{}  ...", "│".bright_black());
    for line in new.lines().take(3) { println!("{} {}", "│".bright_black(), format!("+ {}", line).green()); }
    println!("{}\n", "╰──────────────────────────".bright_black());
}

// --- MAIN ---

fn main() {
    ensure_environment();
    if env::var("CYGNIS_API_KEY").is_err() {
        ask_for_api_key();
    }

    let model = env::var("CYGNIS_MODEL").unwrap_or_else(|_| DEFAULT_MODEL.to_string());
    let mut cli = LiveCli::new(model).unwrap();

    print!("\x1b[2J\x1b[1;1H"); // Clear
    boot_sequence();
    print_prestige_dashboard(&cli.model);

    loop {
        let prompt_prefix = "cygnis".truecolor(255, 140, 0).bold();
        let arrow = "❯".truecolor(255, 215, 0);
        let ghost = "Describe your task...".bright_black();

        print!("{} {} {} \x1b[{}D", prompt_prefix, arrow, ghost, ghost.len() + 1);
        io::stdout().flush().unwrap();

        let mut input = String::new();
        io::stdin().read_line(&mut input).unwrap();

        print!("\x1b[1A\x1b[K"); // Clear the prompt line
        let trimmed = input.trim();
        if trimmed.is_empty() { continue; }
        if trimmed == "/exit" { break; }

        println!("{} {} {}", prompt_prefix, arrow, trimmed.white());
        cli.run_turn(trimmed).unwrap();
    }
}

fn handle_theme_selection() {
    let bold = "\x1b[1m";
    let reset = "\x1b[0m";
    println!("\n  {}Let's get started.{}", bold, reset);
    println!("  Choose the text style that looks best with your terminal\n");
    println!("    1. Dark mode (default)\n    2. Light mode\n    3. Dark mode (colorblind)\n    4. Dark mode (ANSI only)");
    print!("\n  \x1b[38;5;208m❯\x1b[0m Choose a theme [1-4]: ");
    io::stdout().flush().unwrap();
    let mut choice = String::new();
    io::stdin().read_line(&mut choice).unwrap();
    let theme = match choice.trim() { "2" => "Light", "3" => "Colorblind", "4" => "ANSI", _ => "Dark" };
    let _ = save_config("CYGNIS_THEME", theme);
    env::set_var("CYGNIS_THEME", theme);
}

fn ask_for_api_key() {
    println!("\n  CONFIGURATION REQUIRED");
    print!("  \x1b[38;5;208m❯\x1b[0m Enter Anthropic API Key: ");
    io::stdout().flush().unwrap();
    let mut key = String::new();
    io::stdin().read_line(&mut key).unwrap();
    let trimmed = key.trim();
    if !trimmed.is_empty() {
        let _ = save_config("CYGNIS_API_KEY", trimmed);
        env::set_var("CYGNIS_API_KEY", trimmed);
    }
}

struct LiveCli {
    model: String,
    runtime: ConversationRuntime<CygnisRuntimeClient, CliToolExecutor>,
}

impl LiveCli {
    fn new(model: String) -> Result<Self, Box<dyn std::error::Error>> {
        let client = CygnisRuntimeClient::new(model.clone())?;
        let index = get_project_index();
        let runtime = ConversationRuntime::new_with_features(
            Session::new(), client, CliToolExecutor,
            PermissionPolicy::new(PermissionMode::DangerFullAccess),
            vec![format!("You are CYGNIS CODE v2.5. Project Index:\n{}\nCWD: {}", index, env::current_dir().unwrap_or_default().display())],
            &runtime::RuntimeFeatureConfig::default(),
        );
        Ok(Self { model, runtime })
    }

    fn run_turn(&mut self, input: &str) -> Result<(), Box<dyn std::error::Error>> {
        let pb = ProgressBar::new_spinner();
        pb.set_style(ProgressStyle::default_spinner()
            .template("{spinner:.magenta} {msg}")
            .unwrap()
            .tick_chars("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"));
        pb.set_message("Cygnis thinking...".bright_black().to_string());
        pb.enable_steady_tick(Duration::from_millis(100));

        let result = self.runtime.run_turn(input, Some(&mut CliPermissionPrompter));
        pb.finish_and_clear();

        let res = result?;
        println!("\n{}", TerminalRenderer::new().markdown_to_ansi(&final_assistant_text(&res)));
        Ok(())
    }
}

// --- AGENT CAPABILITIES ---

struct CygnisRuntimeClient {
    client: CygnisClient,
    model: String,
    runtime: tokio::runtime::Runtime,
}

impl CygnisRuntimeClient {
    fn new(model: String) -> Result<Self, Box<dyn std::error::Error>> {
        let auth = AuthSource::from_env().map_err(|e| io::Error::new(io::ErrorKind::Other, e.to_string()))?;
        Ok(Self { client: CygnisClient::from_auth(auth), model, runtime: tokio::runtime::Runtime::new()? })
    }
}

impl ApiClient for CygnisRuntimeClient {
    fn stream(&mut self, request: ApiRequest) -> Result<Vec<AssistantEvent>, RuntimeError> {
        let tools = vec![
            ToolDefinition {
                name: "read_file".into(),
                description: Some("Reads a file.".into()),
                input_schema: json!({"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}),
            },
            ToolDefinition {
                name: "write_file".into(),
                description: Some("Writes a file.".into()),
                input_schema: json!({"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}),
            },
            ToolDefinition {
                name: "bash".into(),
                description: Some("Runs a terminal command.".into()),
                input_schema: json!({"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}),
            }
        ];

        let req = MessageRequest {
            model: self.model.clone(),
            max_tokens: 4096,
            messages: convert_messages(&request.messages),
            system: Some(request.system_prompt.join("\n")),
            tools: Some(tools), tool_choice: Some(ToolChoice::Auto), stream: true,
        };

        self.runtime.block_on(async {
            let stream_res = self.client.stream_message(&req).await;
            let mut stream = match stream_res {
                Ok(s) => ApiMessageStream::Cygnis(s),
                Err(e) => return Err(RuntimeError::new(e.to_string())),
            };
            let mut events = Vec::new();
            while let Some(event) = stream.next_event().await.unwrap_or(None) {
                if let ApiStreamEvent::ContentBlockDelta(d) = event {
                    if let ContentBlockDelta::TextDelta { text } = d.delta {
                        print!("{}", text); io::stdout().flush().unwrap();
                        events.push(AssistantEvent::TextDelta(text));
                    }
                }
            }
            events.push(AssistantEvent::MessageStop); Ok(events)
        })
    }
}

struct CliToolExecutor;
impl ToolExecutor for CliToolExecutor {
    fn execute(&mut self, name: &str, input: &str) -> Result<String, ToolError> {
        let val: serde_json::Value = serde_json::from_str(input).unwrap_or_default();
        match name {
            "read_file" => {
                let path = val["path"].as_str().ok_or(ToolError::new("Missing path"))?;
                println!(" {} Reading {}", " ● ".green(), path.white());
                fs::read_to_string(path).map_err(|e| ToolError::new(e.to_string()))
            },
            "bash" => {
                let cmd = val["command"].as_str().ok_or(ToolError::new("Missing command"))?;
                println!(" {} Executing: {}", " ● ".bright_magenta(), cmd.bright_black());
                let out = if cfg!(target_os = "windows") { Command::new("cmd").args(["/C", cmd]).output() } else { Command::new("sh").args(["-c", cmd]).output() };
                let o = out.map_err(|e| ToolError::new(e.to_string()))?;
                Ok(format!("Stdout: {}\nStderr: {}", String::from_utf8_lossy(&o.stdout), String::from_utf8_lossy(&o.stderr)))
            },
            "write_file" => {
                let path = val["path"].as_str().ok_or(ToolError::new("Missing path"))?;
                let content = val["content"].as_str().ok_or(ToolError::new("Missing content"))?;
                print_diff(path, &fs::read_to_string(path).unwrap_or_default(), content);
                print!("  {} Apply changes? [y/n] ", "❯".bright_magenta()); io::stdout().flush().unwrap();
                let mut ans = String::new(); io::stdin().read_line(&mut ans).unwrap();
                if ans.trim().to_lowercase() == "y" { fs::write(path, content).map_err(|e| ToolError::new(e.to_string()))?; Ok("Updated.".into()) } else { Err(ToolError::new("Rejected")) }
            },
            _ => Err(ToolError::new("Unknown tool")),
        }
    }
}

struct CliPermissionPrompter;
impl runtime::PermissionPrompter for CliPermissionPrompter {
    fn decide(&mut self, _: &runtime::PermissionRequest) -> runtime::PermissionPromptDecision { runtime::PermissionPromptDecision::Allow }
}

fn convert_messages(msgs: &[ConversationMessage]) -> Vec<InputMessage> {
    msgs.iter().map(|m| {
        let role = match m.role {
            MessageRole::Assistant => "assistant",
            _ => "user",
        };
        let mut content = Vec::new();
        for b in &m.blocks {
            match b {
                ContentBlock::Text { text } => content.push(InputContentBlock::Text { text: text.clone() }),
                ContentBlock::ToolUse { id, name, input } => content.push(InputContentBlock::ToolUse { id: id.clone(), name: name.clone(), input: serde_json::from_str(input).unwrap_or_default() }),
                ContentBlock::ToolResult { tool_use_id, output, is_error, .. } => content.push(InputContentBlock::ToolResult { tool_use_id: tool_use_id.clone(), content: vec![ToolResultContentBlock::Text { text: output.clone() }], is_error: *is_error }),
            }
        }
        InputMessage { role: role.to_string(), content }
    }).collect()
}

fn final_assistant_text(summary: &runtime::TurnSummary) -> String {
    summary.assistant_messages.last().map(|m| m.blocks.iter().filter_map(|b| if let ContentBlock::Text { text } = b { Some(text.clone()) } else { None }).collect::<Vec<_>>().join("")).unwrap_or_default()
}

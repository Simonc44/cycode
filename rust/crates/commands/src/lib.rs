use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CommandManifestEntry {
    pub name: String,
    pub source: CommandSource,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CommandSource {
    Builtin,
    InternalOnly,
    FeatureGated,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct CommandRegistry {
    entries: Vec<CommandManifestEntry>,
}

impl CommandRegistry {
    #[must_use]
    pub fn new(entries: Vec<CommandManifestEntry>) -> Self {
        Self { entries }
    }
    #[must_use]
    pub fn entries(&self) -> &[CommandManifestEntry] {
        &self.entries
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct SlashCommandSpec {
    pub name: &'static str,
    pub aliases: &'static [&'static str],
    pub summary: &'static str,
    pub argument_hint: Option<&'static str>,
    pub resume_supported: bool,
}

pub const SLASH_COMMAND_SPECS: &[SlashCommandSpec] = &[
    SlashCommandSpec { name: "help", aliases: &[], summary: "Show available slash commands", argument_hint: None, resume_supported: true },
    SlashCommandSpec { name: "status", aliases: &[], summary: "Show current session status", argument_hint: None, resume_supported: true },
    SlashCommandSpec { name: "model", aliases: &[], summary: "Show or switch the active model", argument_hint: Some("[model]"), resume_supported: false },
    SlashCommandSpec { name: "theme", aliases: &[], summary: "Switch the terminal color theme", argument_hint: Some("[theme-name]"), resume_supported: true },
    SlashCommandSpec { name: "init", aliases: &[], summary: "Create a starter CLAUDE.md for this repo", argument_hint: None, resume_supported: true },
    SlashCommandSpec { name: "clear", aliases: &[], summary: "Start a fresh local session", argument_hint: Some("[--confirm]"), resume_supported: true },
    SlashCommandSpec { name: "diff", aliases: &[], summary: "Show git diff for current workspace changes", argument_hint: None, resume_supported: true },
    SlashCommandSpec { name: "exit", aliases: &["quit"], summary: "Exit the REPL session", argument_hint: None, resume_supported: false },
    SlashCommandSpec { name: "config", aliases: &[], summary: "Inspect config files", argument_hint: Some("[section]"), resume_supported: true },
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SlashCommand {
    Help,
    Status,
    Model { model: Option<String> },
    Theme { name: Option<String> },
    Init,
    Clear { confirm: bool },
    Diff,
    Exit,
    Config { section: Option<String> },
    Unknown(String),
}

impl SlashCommand {
    pub fn parse(input: &str) -> Option<Self> {
        let trimmed = input.trim();
        if !trimmed.starts_with('/') { return None; }
        let parts: Vec<&str> = trimmed.trim_start_matches('/').split_whitespace().collect();
        if parts.is_empty() { return None; }

        match parts[0] {
            "help" => Some(SlashCommand::Help),
            "status" => Some(SlashCommand::Status),
            "model" => Some(SlashCommand::Model { model: parts.get(1).map(|s| s.to_string()) }),
            "theme" => Some(SlashCommand::Theme { name: parts.get(1).map(|s| s.to_string()) }),
            "init" => Some(SlashCommand::Init),
            "clear" => Some(SlashCommand::Clear { confirm: parts.contains(&"--confirm") }),
            "diff" => Some(SlashCommand::Diff),
            "exit" | "quit" => Some(SlashCommand::Exit),
            "config" => Some(SlashCommand::Config { section: parts.get(1).map(|s| s.to_string()) }),
            _ => Some(SlashCommand::Unknown(parts[0].to_string())),
        }
    }
}

pub fn render_slash_command_help() -> String {
    let mut help = String::from("\x1b[1;38;5;208mCYGNIS CODE - Commands\x1b[0m\n");
    help.push_str("────────────────────────────────────────────────────────────────────────────\n");
    for spec in SLASH_COMMAND_SPECS {
        let cmd = format!("/{}", spec.name);
        help.push_str(&format!("  \x1b[1m{:<15}\x1b[0m {}\n", cmd, spec.summary));
    }
    help
}

pub fn handle_agents_slash_command(_: Option<&str>, _: &Path) -> std::io::Result<String> { Ok("Agents logic".into()) }
pub fn handle_mcp_slash_command(_: Option<&str>, _: &Path) -> Result<String, String> { Ok("MCP logic".into()) }
pub fn handle_skills_slash_command(_: Option<&str>, _: &Path) -> std::io::Result<String> { Ok("Skills logic".into()) }
pub fn resume_supported_slash_commands() -> Vec<&'static SlashCommandSpec> {
    SLASH_COMMAND_SPECS.iter().filter(|s| s.resume_supported).collect()
}
pub fn slash_command_specs() -> &'static [SlashCommandSpec] { SLASH_COMMAND_SPECS }
pub fn validate_slash_command_input(_: &str) -> Result<Option<SlashCommand>, String> { Ok(None) }

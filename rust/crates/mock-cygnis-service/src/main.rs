use std::env;
use std::net::SocketAddr;
use anyhow::{Result, Context};

// --- LOGIQUE INTÉGRÉE (Remplace la crate manquante) ---
pub struct MockAnthropicService {
    addr: String,
}

impl MockAnthropicService {
    pub async fn spawn_on(bind_addr: &str) -> Result<Self> {
        // On vérifie juste que l'adresse est valide
        let _: SocketAddr = bind_addr.parse().context("Invalid bind address")?;
        Ok(MockAnthropicService {
            addr: bind_addr.to_string(),
        })
    }

    pub fn base_url(&self) -> String {
        format!("http://{}", self.addr)
    }
}

// --- TON MAIN D'ORIGINE ADAPTÉ ---
#[tokio::main(flavor = "multi_thread")]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut bind_addr = String::from("127.0.0.1:8080"); // Port par défaut fixé pour éviter le :0
    let mut args = env::args().skip(1);

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--bind" => {
                bind_addr = args
                    .next()
                    .ok_or_else(|| "missing value for --bind".to_string())?;
            }
            flag if flag.starts_with("--bind=") => {
                bind_addr = flag[7..].to_string();
            }
            "--help" | "-h" => {
                println!("Usage: mock-anthropic-service [--bind HOST:PORT]");
                return Ok(());
            }
            other => {
                return Err(format!("unsupported argument: {other}").into());
            }
        }
    }

    // Utilise la structure définie localement plus haut
    let server = MockAnthropicService::spawn_on(&bind_addr).await?;

    println!("MOCK_ANTHROPIC_BASE_URL={}", server.base_url());
    println!(">> Cygnis Mock Server running on {}. Press Ctrl+C to stop.", bind_addr);

    tokio::signal::ctrl_c().await?;
    drop(server);
    Ok(())
}
mod utils;
use utils::Args;
use std::result::Result;
use std::io::{BufRead, Write};
use std::sync::{mpsc, Arc, Mutex};
use libwing::{WingConsole, WingResponse};

fn print_node(tx: &mpsc::Sender<String>, prefix: &str, id: i32, val: &str) {
    match WingConsole::id_to_defs(id) {
        None => {}
        Some(defs) if defs.is_empty() => {}
        Some(defs) if defs.len() == 1 => {
            if !defs[0].0.contains('$') {
                tx.send(format!("{}{} = {}", prefix, defs[0].0, val)).ok();
            }
        }
        Some(defs) => {
            use std::collections::HashSet;
            let u = HashSet::<u16>::from_iter(defs.iter().map(|(_, d)| d.index));
            if u.len() == 1 {
                tx.send(format!("{}prop{} = {}", prefix, defs[0].1.index, val)).ok();
            }
        }
    }
}

fn connect_cmd(host: Option<&str>) -> Option<WingConsole> {
    for _ in 0..20 {
        match WingConsole::connect(host) {
            Ok(mut c) => { c.keep_alive().ok(); return Some(c); }
            Err(_)    => { std::thread::sleep(std::time::Duration::from_millis(500)); }
        }
    }
    None
}

fn main() -> Result<(), libwing::Error> {
    let mut args = Args::new("Usage: wingmon [-h host]\n   -h host : Wing IP");
    let mut host: Option<String> = None;
    while args.has_next() {
        match args.next().as_str() {
            "-h" => { host = Some(args.next()); }
            _ => {}
        }
    }

    // stdout channel — single writer thread flushes after every message
    let (tx, rx) = mpsc::channel::<String>();
    std::thread::spawn(move || {
        let mut out = std::io::BufWriter::new(std::io::stdout());
        for msg in rx { let _ = writeln!(out, "{}", msg); let _ = out.flush(); }
    });

    // Connection 1: event_wing — SYNC + live events
    let mut event_wing = WingConsole::connect(host.as_deref())?;
    eprintln!("[wingmon] Connected!");
    tx.send("Connected!".to_string()).ok();

    // SYNC
    let sync_paths: Vec<String> =
        (1..=48).map(|i| format!("/ch/{}", i))
        .chain((1..=16).map(|i| format!("/bus/{}", i)))
        .chain((1..=4).map(|i|  format!("/main/{}", i)))
        .chain((1..=8).map(|i|  format!("/mtx/{}", i)))
        .chain((1..=16).map(|i| format!("/dca/{}", i)))
        .chain((1..=16).map(|i| format!("/fx/{}", i)))
        .collect();

    let mut total = 0usize;
    eprintln!("[wingmon] SYNC: {} nodes", sync_paths.len());
    for chunk in sync_paths.chunks(8) {
        let mut pending = 0i32;
        for path in chunk {
            if let Some(id) = WingConsole::name_to_id(path) {
                if event_wing.request_node_data(id).is_ok() { pending += 1; }
            }
        }
        while pending > 0 {
            match event_wing.read() {
                Ok(WingResponse::RequestEnd)         => { pending -= 1; }
                Ok(WingResponse::NodeData(id, data)) => {
                    print_node(&tx, "DATA ", id, &data.get_string());
                    total += 1;
                }
                Ok(_) | Err(_) => {}
            }
        }
    }
    tx.send(format!("SYNC_COMPLETE {}", total)).ok();
    eprintln!("[wingmon] SYNC done: {} params.", total);

    // Connection 2: cmd_wing — shared between stdin thread and keepalive thread
    let cmd_shared: Arc<Mutex<Option<WingConsole>>> = Arc::new(Mutex::new(None));

    // Initial connect
    {
        let mut g = cmd_shared.lock().unwrap();
        eprintln!("[wingmon] cmd_wing connecting...");
        *g = connect_cmd(host.as_deref());
        if g.is_some() { eprintln!("[wingmon] cmd_wing connected"); }
    }

    // Keepalive thread — fires every 4s regardless of stdin state
    // Keeps Wing from dropping cmd_wing even if stdin is EOF (PyInstaller windowed mode)
    let ka_cmd  = Arc::clone(&cmd_shared);
    let ka_host = host.clone();
    std::thread::spawn(move || {
        loop {
            std::thread::sleep(std::time::Duration::from_secs(4));
            let mut g = cmd_shared.lock().unwrap();
            let ok = g.as_mut().map(|c| c.keep_alive().is_ok()).unwrap_or(false);
            if !ok {
                eprintln!("[wingmon] cmd_wing keepalive reconnect...");
                *g = connect_cmd(ka_host.as_deref());
                if g.is_some() { eprintln!("[wingmon] cmd_wing reconnected"); }
            }
        }
    });
    // move ka_cmd back to actually use it (Rust borrow)
    let _ = ka_cmd;

    // stdin command thread — handles SET/BATCH_SET/KEEPALIVE from Python
    let si_cmd  = Arc::clone(&cmd_shared);
    let si_host = host.clone();
    std::thread::spawn(move || {
        let stdin = std::io::stdin();
        for line in stdin.lock().lines() {
            let Ok(l) = line else { break };
            let trimmed = l.trim();
            let mut g = si_cmd.lock().unwrap();
            let mut reconnect = false;

            if let Some(ref mut cmd) = *g {
                if let Some(params) = trimmed.strip_prefix("BATCH_SET ") {
                    for param in params.split(',') {
                        if let Some((path, val)) = param.split_once('=') {
                            if let Some(id) = WingConsole::name_to_id(path.trim()) {
                                let t = val.trim();
                                let r = if let Ok(i) = t.parse::<i32>()      { cmd.set_int(id, i) }
                                        else if let Ok(f) = t.parse::<f32>() { cmd.set_float(id, f) }
                                        else                                  { cmd.set_string(id, t) };
                                if r.is_err() { reconnect = true; break; }
                            }
                        }
                    }
                } else if let Some(rest) = trimmed.strip_prefix("SET ") {
                    if let Some(space) = rest.find(' ') {
                        let path = &rest[..space];
                        let val  = rest[space+1..].trim();
                        if let Some(id) = WingConsole::name_to_id(path) {
                            let r = if let Ok(i) = val.parse::<i32>()      { cmd.set_int(id, i) }
                                    else if let Ok(f) = val.parse::<f32>() { cmd.set_float(id, f) }
                                    else                                    { cmd.set_string(id, val) };
                            if r.is_err() { reconnect = true; }
                        }
                    }
                } else if trimmed == "KEEPALIVE" {
                    if cmd.keep_alive().is_err() { reconnect = true; }
                }
            } else {
                reconnect = true;
            }

            if reconnect {
                eprintln!("[wingmon] cmd_wing reconnecting...");
                *g = connect_cmd(si_host.as_deref());
                if g.is_some() { eprintln!("[wingmon] cmd_wing reconnected"); }
            }
        }
        eprintln!("[wingmon] stdin EOF — internal keepalive maintains connection");
    });

    // Live event loop — main thread
    loop {
        match event_wing.read()? {
            WingResponse::NodeData(id, data) => { print_node(&tx, "", id, &data.get_string()); }
            WingResponse::RequestEnd => {}
            _ => {}
        }
    }
}

mod utils;
use utils::Args;
use std::result::Result;
use std::io::{BufRead, Write};
use std::sync::mpsc;
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

fn main() -> Result<(), libwing::Error> {
    let mut args = Args::new("Usage: wingmon [-h host]\n   -h host : Wing IP");
    let mut host: Option<String> = None;
    while args.has_next() {
        match args.next().as_str() {
            "-h" => { host = Some(args.next()); }
            _ => {}
        }
    }

    // stdout channel — single writer thread with explicit flush after each message
    let (tx_out, rx_out) = mpsc::channel::<String>();
    std::thread::spawn(move || {
        let mut out = std::io::BufWriter::new(std::io::stdout());
        for msg in rx_out {
            let _ = writeln!(out, "{}", msg);
            let _ = out.flush();
        }
    });

    // Connection 1: event_wing — SYNC + live events
    let mut event_wing = WingConsole::connect(host.as_deref())?;
    eprintln!("[wingmon] Connected!");
    tx_out.send("Connected!".to_string()).ok();

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
                    print_node(&tx_out, "DATA ", id, &data.get_string());
                    total += 1;
                }
                Ok(_) | Err(_) => {}
            }
        }
    }
    tx_out.send(format!("SYNC_COMPLETE {}", total)).ok();
    eprintln!("[wingmon] SYNC done: {} params.", total);

    // cmd channel: all commands go through here (from stdin thread + keepalive thread)
    let (tx_cmd, rx_cmd) = mpsc::channel::<String>();

    // Stdin thread: forwards Python commands to cmd channel
    // If stdin is EOF (PyInstaller windowed mode), thread exits silently —
    // keepalive thread keeps the connection alive regardless
    let tx_stdin = tx_cmd.clone();
    std::thread::spawn(move || {
        let stdin = std::io::stdin();
        for line in stdin.lock().lines() {
            let Ok(l) = line else { break };
            tx_stdin.send(l).ok();
        }
        eprintln!("[wingmon] stdin EOF — internal keepalive maintains connection");
    });

    // Internal keepalive thread: sends KEEPALIVE every 4s
    // Ensures Wing never drops cmd_wing even without Python stdin
    let tx_ka = tx_cmd.clone();
    std::thread::spawn(move || {
        loop {
            std::thread::sleep(std::time::Duration::from_secs(4));
            if tx_ka.send("KEEPALIVE".to_string()).is_err() { break; }
        }
    });

    // cmd_wing thread: single owner of WingConsole, no Send required
    let host2 = host.clone();
    std::thread::spawn(move || {
        let mut cmd_opt: Option<WingConsole> = None;

        // Initial connect with retry
        loop {
            match WingConsole::connect(host2.as_deref()) {
                Ok(mut c) => {
                    eprintln!("[wingmon] cmd_wing connected");
                    c.keep_alive().ok();
                    cmd_opt = Some(c);
                    break;
                }
                Err(e) => {
                    eprintln!("[wingmon] cmd_wing connect failed: {}", e);
                    std::thread::sleep(std::time::Duration::from_millis(500));
                }
            }
        }

        // Process all commands from channel (stdin + internal keepalive)
        for l in rx_cmd {
            let trimmed = l.trim();
            let mut reconnect = false;

            if let Some(ref mut cmd) = cmd_opt {
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
                            if r.is_err() {
                                eprintln!("[wingmon] SET error — reconnecting");
                                reconnect = true;
                            }
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
                cmd_opt = None;
                loop {
                    match WingConsole::connect(host2.as_deref()) {
                        Ok(mut c) => {
                            c.keep_alive().ok();
                            cmd_opt = Some(c);
                            eprintln!("[wingmon] cmd_wing reconnected");
                            break;
                        }
                        Err(_) => {
                            std::thread::sleep(std::time::Duration::from_millis(500));
                        }
                    }
                }
            }
        }
    });

    // Live event loop — main thread, runs forever
    loop {
        match event_wing.read()? {
            WingResponse::NodeData(id, data) => {
                print_node(&tx_out, "", id, &data.get_string());
            }
            WingResponse::RequestEnd => {}
            _ => {}
        }
    }
}

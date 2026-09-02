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

    let (tx, rx) = mpsc::channel::<String>();
    std::thread::spawn(move || {
        let mut out = std::io::BufWriter::new(std::io::stdout());
        for msg in rx { let _ = writeln!(out, "{}", msg); let _ = out.flush(); }
    });

    // Connection 1: event_wing — SYNC + live events (blocking reads, no timeout)
    let mut event_wing = WingConsole::connect(host.as_deref())?;
    eprintln!("[wingmon] Connected!");
    tx.send("Connected!".to_string()).ok();

    // SYNC on event_wing — subscribes us to all nodes
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
    eprintln!("[wingmon] SYNC done: {} params. event_wing now receives all live events.", total);

    // Connection 2: cmd_wing — SET/KEEPALIVE only, NEVER reads
    // Does NOT call request_node_data so event subscriptions stay on event_wing
    let host2 = host.clone();
    std::thread::spawn(move || {
        // Buffer commands while connecting/reconnecting
        let stdin = std::io::stdin();
        let mut cmd_opt: Option<WingConsole> = None;

        // Connect with retry
        loop {
            match WingConsole::connect(host2.as_deref()) {
                Ok(c) => { eprintln!("[wingmon] cmd_wing connected"); let mut c = c; c.keep_alive().ok(); cmd_opt = Some(c); break; }
                Err(e) => { eprintln!("[wingmon] cmd_wing connect failed: {}", e); std::thread::sleep(std::time::Duration::from_millis(500)); }
            }
        }

        for line in stdin.lock().lines() {
            let Ok(l) = line else { break };
            let trimmed = l.trim();
            if cmd_opt.is_none() { continue; }

            let mut reconnect = false;
            {
                let cmd = cmd_opt.as_mut().unwrap();

                if let Some(params) = trimmed.strip_prefix("BATCH_SET ") {
                    // strip_prefix avoids splitn issues with spaces in string values (names)
                    for param in params.split(',') {
                        if let Some((path, val)) = param.split_once('=') {
                            if let Some(id) = WingConsole::name_to_id(path.trim()) {
                                let t = val.trim();
                                let result = if let Ok(i) = t.parse::<i32>()      { cmd.set_int(id, i) }
                                             else if let Ok(f) = t.parse::<f32>() { cmd.set_float(id, f) }
                                             else                                  { cmd.set_string(id, t) };
                                if result.is_err() { reconnect = true; break; }
                            }
                        }
                    }
                } else if let Some(rest) = trimmed.strip_prefix("SET ") {
                    // SET path value — value may contain spaces (channel names)
                    if let Some(space) = rest.find(' ') {
                        let path = &rest[..space];
                        let val  = rest[space+1..].trim();
                        if let Some(id) = WingConsole::name_to_id(path) {
                            let result = if let Ok(i) = val.parse::<i32>()      { cmd.set_int(id, i) }
                                         else if let Ok(f) = val.parse::<f32>() { cmd.set_float(id, f) }
                                         else                                    { cmd.set_string(id, val) };
                            if let Err(e) = result {
                                eprintln!("[wingmon] SET error: {} — reconnecting", e);
                                reconnect = true;
                            }
                        }
                    }
                } else if trimmed == "KEEPALIVE" {
                    cmd.keep_alive().ok();
                }
            } // cmd borrow ends here
            if reconnect {
                eprintln!("[wingmon] cmd_wing reconnecting...");
                cmd_opt = WingConsole::connect(host2.as_deref()).ok();
                if cmd_opt.is_some() { eprintln!("[wingmon] cmd_wing reconnected"); }
            }
        }
    });

    // Live event loop on event_wing — blocking, no timeout
    loop {
        match event_wing.read()? {
            WingResponse::NodeData(id, data) => {
                print_node(&tx, "", id, &data.get_string());
            }
            WingResponse::RequestEnd => {}
            _ => {}
        }
    }
}

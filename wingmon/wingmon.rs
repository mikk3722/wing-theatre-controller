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

/// Encode one parameter as Wing binary: d7 [4-byte hash] [compact value]
/// Matches Wing Editor's wire format exactly.
/// Hash bytes containing 0xdf are escaped with 0xde (Wing protocol requirement).
fn encode_param(path: &str, val: &str) -> Option<Vec<u8>> {
    let id = WingConsole::name_to_id(path)?;
    let id_bytes = id.to_be_bytes();

    // Escape 0xdf bytes in hash (Wing protocol)
    let mut buf = vec![0xd7u8];
    for b in id_bytes {
        if b == 0xdf { buf.push(0xde); }
        buf.push(b);
    }

    let val = val.trim();

    // Try integer
    if let Ok(i) = val.parse::<i32>() {
        if i >= 0 && i <= 127 {
            buf.push(i as u8);
        } else {
            let b = i.to_be_bytes();
            buf.extend_from_slice(&[0xd4, b[0], b[1], b[2], b[3]]);
        }
        return Some(buf);
    }

    // Try float
    if let Ok(f) = val.parse::<f32>() {
        let b = f.to_be_bytes();
        buf.extend_from_slice(&[0xd5, b[0], b[1], b[2], b[3]]);
        return Some(buf);
    }

    // String
    let bytes = val.as_bytes();
    let len = bytes.len();
    if len == 0 {
        buf.push(0xd0);
    } else if len <= 64 {
        buf.push(0x7f + len as u8);
    } else if len <= 256 {
        buf.push(0xd1);
        buf.push((len - 1) as u8);
    } else {
        return None; // too long
    }
    buf.extend_from_slice(bytes);
    Some(buf)
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

    // stdout channel - single writer thread, explicit flush after every message
    let (tx_out, rx_out) = mpsc::channel::<String>();
    std::thread::spawn(move || {
        let mut out = std::io::BufWriter::new(std::io::stdout());
        for msg in rx_out { let _ = writeln!(out, "{}", msg); let _ = out.flush(); }
    });

    // Connection 1: event_wing - SYNC + live events
    let mut event_wing = WingConsole::connect(host.as_deref())?;
    event_wing.set_nodelay();
    // Override libwing's short read timeout - prevents spurious OS 10060 on Windows.
    // Real disconnections are detected via cmd_wing keepalive failures instead.
    event_wing.set_read_timeout_secs(60); // periodic wake-up so we can send keepalive
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

    // Shared flag: set by cmd_wing when Wing is truly dead
    let wing_dead = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
    let wing_dead_cmd = std::sync::Arc::clone(&wing_dead);

    // cmd channel: stdin + internal keepalive both feed here
    let (tx_cmd, rx_cmd) = mpsc::channel::<String>();

    // Stdin thread - forwards Python commands to cmd channel
    let tx_stdin = tx_cmd.clone();
    std::thread::spawn(move || {
        let stdin = std::io::stdin();
        for line in stdin.lock().lines() {
            let Ok(l) = line else { break };
            // Diagnostic: log first word of every command received on stdin,
            // so we can confirm Python -> wingmon delivery is working.
            let verb = l.trim().split(' ').next().unwrap_or("");
            let len = l.len();
            eprintln!("[wingmon] stdin recv: {} ({} bytes)", verb, len);
            tx_stdin.send(l).ok();
        }
        eprintln!("[wingmon] stdin EOF - internal keepalive maintains connection");
    });

    // Internal keepalive thread - every 4s regardless of stdin state
    let tx_ka = tx_cmd.clone();
    std::thread::spawn(move || {
        loop {
            std::thread::sleep(std::time::Duration::from_secs(4));
            if tx_ka.send("KEEPALIVE".to_string()).is_err() { break; }
        }
    });

    // cmd_wing thread - single owner of cmd WingConsole
    // Also health monitor: repeated keepalive failures = Wing is gone -> DEAD signal
    let host2 = host.clone();
    std::thread::spawn(move || {
        let mut cmd_opt: Option<WingConsole> = None;
        let mut dead_count = 0u32;

        loop {
            match WingConsole::connect(host2.as_deref()) {
                Ok(mut c) => {
                    eprintln!("[wingmon] cmd_wing connected");
                    c.set_nodelay();
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

        for l in rx_cmd {
            let trimmed = l.trim();
            let mut reconnect = false;

            if let Some(ref mut cmd) = cmd_opt {
                if let Some(params) = trimmed.strip_prefix("BATCH_SET ") {
                    // Small bursts (matching Wing Editor's wire behaviour),
                    // sent back-to-back with no artificial delay. TCP_NODELAY
                    // is enabled on this connection so each write goes out
                    // immediately rather than waiting on Nagle's algorithm.
                    const CHUNK: usize = 4;
                    let all_params: Vec<&str> = params.split(',').collect();
                    let mut sent_bytes = 0usize;
                    let mut chunk_count = 0usize;
                    let mut had_error = false;
                    let t0 = std::time::Instant::now();

                    for group in all_params.chunks(CHUNK) {
                        let mut buf: Vec<u8> = vec![0xdf, 0xd1];
                        for param in group {
                            if let Some((path, val)) = param.split_once('=') {
                                if let Some(encoded) = encode_param(path.trim(), val) {
                                    buf.extend_from_slice(&encoded);
                                }
                            }
                        }
                        if buf.len() > 2 {
                            match cmd.write_raw(&buf) {
                                Ok(_) => {
                                    sent_bytes += buf.len();
                                    chunk_count += 1;
                                }
                                Err(e) => {
                                    let s = e.to_string();
                                    eprintln!("[wingmon] BATCH_SET chunk {} FAILED: {}", chunk_count, s);
                                    if s.contains("10060") || s.contains("timed out") {
                                        std::thread::sleep(std::time::Duration::from_millis(500));
                                    }
                                    had_error = true;
                                    break;
                                }
                            }
                        }
                    }

                    if had_error {
                        reconnect = true;
                    } else {
                        eprintln!("[wingmon] BATCH_SET sent: {} bytes in {} bursts, {}ms",
                            sent_bytes, chunk_count, t0.elapsed().as_millis());
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
                cmd_opt = None;
                let mut ok = false;
                for _ in 0..3 {
                    if let Ok(mut c) = WingConsole::connect(host2.as_deref()) {
                        c.set_nodelay();
                        c.keep_alive().ok();
                        cmd_opt = Some(c);
                        dead_count = 0;
                        c.set_nodelay();
                        eprintln!("[wingmon] cmd_wing reconnected");
                        ok = true;
                        break;
                    }
                    std::thread::sleep(std::time::Duration::from_millis(500));
                }
                if !ok {
                    dead_count += 1;
                    eprintln!("[wingmon] cmd_wing reconnect failed ({})", dead_count);
                    // 5 failed reconnects ~ 7.5s -> Wing is truly gone
                    if dead_count >= 5 {
                        eprintln!("[wingmon] Wing appears dead - signalling disconnect");
                        wing_dead_cmd.store(true, std::sync::atomic::Ordering::Relaxed);
                        return;
                    }
                }
            }
        }
    });


    // Live event loop. 60s read timeout wakes us periodically so we can:
    //  1. Send a keepalive on event_wing itself - keeps NAT/firewall mapping
    //     alive (routers commonly drop idle TCP after ~5 min of silence)
    //  2. Check the wing_dead flag from cmd_wing's health monitor
    // A timeout here is NORMAL (just means Wing has been quiet) - it is
    // only treated as a real problem if the keepalive write itself fails.
    let mut consecutive_errors = 0u32;
    loop {
        if wing_dead.load(std::sync::atomic::Ordering::Relaxed) {
            eprintln!("[wingmon] Wing confirmed dead - disconnecting");
            return Err(libwing::Error::from(std::io::Error::new(
                std::io::ErrorKind::ConnectionReset, "Wing connection lost")));
        }
        match event_wing.read() {
            Ok(WingResponse::NodeData(id, data)) => {
                consecutive_errors = 0;
                print_node(&tx_out, "", id, &data.get_string());
            }
            Ok(_) => { consecutive_errors = 0; }
            Err(e) => {
                let msg = e.to_string();
                let is_timeout = msg.contains("10060") || msg.contains("timed out")
                    || msg.contains("timeout") || msg.contains("WouldBlock");

                if is_timeout {
                    // Normal - Wing has just been quiet. Re-request a known
                    // parameter (same mechanism used during SYNC) to generate
                    // real Wing-protocol traffic and keep the connection warm
                    // through NAT/firewall idle timeouts. Using keep_alive()
                    // here confused Wing's protocol state on this connection
                    // (it's meant for the command connection, not the event
                    // subscription connection) - this caused GO and live
                    // updates to silently stop working on Windows.
                    let ping_id = WingConsole::name_to_id("/ch/1/mute");
                    let ok = if let Some(id) = ping_id {
                        event_wing.request_node_data(id).is_ok()
                    } else {
                        true // can't resolve path - don't treat as an error
                    };
                    if !ok {
                        consecutive_errors += 1;
                        eprintln!("[wingmon] event_wing keepalive-ping failed #{}", consecutive_errors);
                    } else {
                        consecutive_errors = 0;
                    }
                } else {
                    consecutive_errors += 1;
                    eprintln!("[wingmon] event_wing error #{}: {}", consecutive_errors, e);
                }

                if consecutive_errors > 5 {
                    eprintln!("[wingmon] event_wing unrecoverable - disconnecting");
                    return Err(e);
                }
                if !is_timeout {
                    std::thread::sleep(std::time::Duration::from_millis(500));
                }
            }
        }
    }
}

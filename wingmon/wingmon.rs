mod utils;
use utils::Args;
use std::result::Result;
use std::io::{BufRead, Write};
use std::sync::mpsc;
use libwing::{WingConsole, WingResponse, WingNodeData};

/// Wing's internal/read-only values have a '$' in the name ($fname, $state,
/// $stat ...). The control-surface tree itself is called "$ctl", so that one
/// prefix is allowed -- layers, user controls and surface settings live there.
fn is_internal(name: &str) -> bool {
    // "/$ctl/$globals/srcdisp" = show source name/colour on the strips
    name.replace("/$ctl/$globals/srcdisp", "/srcdisp")
        .replace("/$ctl/", "/")
        .contains('$')
}

fn print_node(tx: &mpsc::Sender<String>, prefix: &str, id: i32, val: &str) {
    match WingConsole::id_to_defs(id) {
        None => {}
        Some(defs) if defs.is_empty() => {}
        Some(defs) if defs.len() == 1 => {
            if !is_internal(&defs[0].0) {
                tx.send(format!("{}{} = {}", prefix, defs[0].0, val)).ok();
            }
        }
        Some(defs) => {
            use std::collections::HashSet;
            let u = HashSet::<u16>::from_iter(defs.iter().map(|(_, d)| d.index));
            if u.len() == 1 {
                // Ambiguous across models (the same index means a different
                // parameter depending on which model is loaded, e.g. index 7
                // is "1q" for EQ model STD but "lmg" for EQ model SOUL --
                // confirmed in Behringer's own Wing Remote Protocols doc).
                // propmap.jsonl only ever documents ONE canonical model per
                // section, so resolving purely from the index can silently
                // apply the WRONG model's parameter name. The raw hash
                // (id) is Wing's own unambiguous address for this exact
                // parameter regardless of model -- send it alongside the
                // index so the value can be captured and recalled by hash
                // directly, with no name/model guessing needed at all.
                //
                // The CHANNEL and SECTION are both structural, not
                // model-dependent -- every candidate def here shares the
                // same channel/section even though their names differ per
                // model -- so it's safe to read them from defs[0]'s own
                // path and send them explicitly. Without this, the
                // receiving side would have to guess which channel+section
                // a bare "propN#hash" event belongs to from whatever it
                // last saw reported -- and during the initial sync (which
                // walks every channel/bus/main/mtx/dca/fx sequentially),
                // that "last seen" context ends up pointing at whichever
                // node happened to sync last, so live events for any OTHER
                // channel get silently misattributed until that channel's
                // own model gets freshly reported again (e.g. by touching
                // the model selector).
                let parts: Vec<&str> = defs[0].0.split('/').collect();
                let (channel, section) = if parts.len() >= 3 && parts[1] == "fx" {
                    (format!("fx/{}", parts[2]), "fx".to_string())
                } else if parts.len() >= 4 {
                    (format!("{}/{}", parts[1], parts[2]), parts[3].to_string())
                } else {
                    (String::new(), String::new())
                };
                if !channel.is_empty() && !section.is_empty() {
                    tx.send(format!("{}{}:{}:prop{}#{:08x} = {}", prefix, channel, section, defs[0].1.index, id as u32, val)).ok();
                }
            }
        }
    }
}

/// Text form of a value as sent to the app. libwing's get_string() prints
/// a whole-number FLOAT without a decimal point (0.0 -> "0", -10.0 -> "-10"),
/// which made e.g. a fader at exactly 0 dB look like the integer 0 -- and it
/// was then sent back to Wing as an int token instead of a float. Floats
/// always keep a decimal point here, so the type survives the round trip
/// (app -> show file -> recall -> encode_param) exactly as Wing sent it.
fn value_string(data: &WingNodeData) -> String {
    if data.has_string() {
        data.get_string()
    } else if data.has_float() {
        fmt_f32(data.get_float())
    } else if data.has_int() {
        data.get_int().to_string()
    } else {
        String::new()
    }
}

fn fmt_f32(f: f32) -> String {
    let s = f.to_string();     // shortest text that reads back as the same f32
    if f.is_finite() && !s.contains('.') && !s.contains('e') {
        format!("{}.0", s)
    } else {
        s
    }
}

/// Encode one parameter as Wing binary: d7 [4-byte hash] [compact value],
/// following the token table in Behringer's "WING Remote Protocols"
/// (Binary Stream Format, channel 2):
///   0x00..0x3f      int 0..63 (single byte)
///   0x40..0x7f      NODE INDEX 1..64 -- NOT a value! (an int 64..127 sent
///                   as one byte here would navigate, not set anything)
///   0x80..0xbf      string of 1..64 bytes, 0xd0 empty string,
///   0xd1 len        string of 1..256 bytes
///   0xd3 word       int16,  0xd4 long int32,  0xd5 long float32
/// The finished bytes are passed through escape_df() -- see there.
fn encode_param(path: &str, val: &str) -> Option<Vec<u8>> {
    // Hash-direct addressing: paths for ambiguous (model-dependent)
    // parameters carry their raw hash embedded as a "#xxxxxxxx" suffix
    // (see print_node) -- e.g. "/ch/5/gate/#a1b2c3d4". The prefix before
    // '#' exists only for the Python side's own channel/section bookkeeping
    // and recall-scope checks; it means nothing to Wing. When present, use
    // the hash directly and skip name_to_id entirely -- this is Wing's own
    // unambiguous addressing (confirmed supported: "WING will accept both
    // OSC path or the native hash data... /ch/1/mute or /#f50f69f8").
    let id = if let Some(hash_str) = path.rsplit('#').next().filter(|_| path.contains('#')) {
        u32::from_str_radix(hash_str, 16).ok().map(|h| h as i32)?
    } else {
        WingConsole::name_to_id(path)?
    };

    let mut raw = vec![0xd7u8];
    raw.extend_from_slice(&id.to_be_bytes());

    let val = val.trim();

    if let Ok(i) = val.parse::<i32>() {
        if (0..=0x3f).contains(&i) {
            raw.push(i as u8);
        } else if (-32768..=32767).contains(&i) {
            let b = (i as i16).to_be_bytes();
            raw.extend_from_slice(&[0xd3, b[0], b[1]]);
        } else {
            let b = i.to_be_bytes();
            raw.extend_from_slice(&[0xd4, b[0], b[1], b[2], b[3]]);
        }
        return Some(escape_df(raw));
    }

    if let Ok(f) = val.parse::<f32>() {
        let b = f.to_be_bytes();
        raw.extend_from_slice(&[0xd5, b[0], b[1], b[2], b[3]]);
        return Some(escape_df(raw));
    }

    // String
    let bytes = val.as_bytes();
    let len = bytes.len();
    if len == 0 {
        raw.push(0xd0);
    } else if len <= 64 {
        raw.push(0x7f + len as u8);
    } else if len <= 256 {
        raw.push(0xd1);
        raw.push((len - 1) as u8);
    } else {
        return None; // too long
    }
    raw.extend_from_slice(bytes);
    Some(escape_df(raw))
}

/// 0xdf is the escape byte of Wing's native protocol: 0xdf followed by
/// 0xd0..0xdd switches the communication channel. A 0xdf that is DATA --
/// inside a hash, an int, a float or a string -- must therefore be sent as
/// 0xdf 0xde ("literal 0xdf"), or Wing may read it together with the next
/// byte as a channel switch (e.g. a float ending in 0xdf followed by the
/// next parameter's 0xd7 = "switch to channel 7"), and every following
/// parameter in that burst is lost. Sending 0xdf 0xde for every data 0xdf
/// is always correct (WING Remote Protocols, sample transmit/receive
/// routines). Previously only hash bytes were escaped, and in the wrong
/// order (0xde 0xdf), which misaligned the hash itself.
fn escape_df(raw: Vec<u8>) -> Vec<u8> {
    let mut out = Vec::with_capacity(raw.len() + 4);
    for b in raw {
        out.push(b);
        if b == 0xdf {
            out.push(0xde);
        }
    }
    out
}

#[cfg(test)]
mod encode_tests {
    use super::*;

    #[test]
    fn small_ints_are_one_byte_only_up_to_63() {
        let e = encode_param("#01020304", "63").unwrap();
        assert_eq!(e, vec![0xd7, 1, 2, 3, 4, 63]);
        let e = encode_param("#01020304", "64").unwrap();
        assert_eq!(e, vec![0xd7, 1, 2, 3, 4, 0xd3, 0x00, 64]);
        let e = encode_param("#01020304", "127").unwrap();
        assert_eq!(e, vec![0xd7, 1, 2, 3, 4, 0xd3, 0x00, 127]);
        let e = encode_param("#01020304", "-1").unwrap();
        assert_eq!(e, vec![0xd7, 1, 2, 3, 4, 0xd3, 0xff, 0xff]);
        let e = encode_param("#01020304", "100000").unwrap();
        assert_eq!(e, vec![0xd7, 1, 2, 3, 4, 0xd4, 0x00, 0x01, 0x86, 0xa0]);
    }

    #[test]
    fn df_in_hash_and_value_is_escaped() {
        let e = encode_param("#01df0304", "1").unwrap();
        assert_eq!(e, vec![0xd7, 1, 0xdf, 0xde, 3, 4, 1]);
        // float whose last byte is 0xdf
        let f = f32::from_be_bytes([0x40, 0x49, 0x0f, 0xdf]);
        let e = encode_param("#01020304", &format!("{}", f)).unwrap();
        assert_eq!(&e[..6], &[0xd7, 1, 2, 3, 4, 0xd5]);
        assert_eq!(&e[6..], &[0x40, 0x49, 0x0f, 0xdf, 0xde]);
    }

    #[test]
    fn floats_keep_their_type_through_the_round_trip() {
        for (f, txt) in [(0.0f32, "0.0"), (-10.0, "-10.0"), (-6.37, "-6.37"),
                         (1234.567, "1234.567"), (0.001, "0.001")] {
            let s = fmt_f32(f);
            assert_eq!(s, txt);
            // what the app sends back must be encoded as the SAME f32
            let e = encode_param("#01020304", &s).unwrap();
            assert_eq!(e[5], 0xd5, "{} must be sent as float32", s);
            let back = f32::from_be_bytes([e[6], e[7], e[8], e[9]]);
            assert_eq!(back.to_bits(), f.to_bits(), "{} changed on the way", s);
        }
        // a real integer stays an integer
        assert_eq!(encode_param("#01020304", "0").unwrap()[5], 0x00);
    }

    #[test]
    fn internal_names() {
        assert!(!is_internal("/$ctl/layer/L/1/name"));
        assert!(!is_internal("/ch/1/fdr"));
        assert!(is_internal("/$ctl/user/gpio/1/bu/$fname"));
        assert!(is_internal("/$stat/time"));
        assert!(!is_internal("/$ctl/$globals/srcdisp"));
        assert!(is_internal("/$ctl/$globals/$savenow"));
    }

    #[test]
    fn strings() {
        assert_eq!(encode_param("#01020304", "").unwrap(), vec![0xd7, 1, 2, 3, 4, 0xd0]);
        assert_eq!(encode_param("#01020304", "BD").unwrap(), vec![0xd7, 1, 2, 3, 4, 0x81, b'B', b'D']);
    }
}

fn main() -> Result<(), libwing::Error> {
    let mut args = Args::new("Usage: wingmon [-h host]\n   -h host : Wing IP");
    let mut host: Option<String> = None;
    let mut encode_test = false;
    while args.has_next() {
        match args.next().as_str() {
            "-h" => { host = Some(args.next()); }
            "--encode-test" => { encode_test = true; }
            _ => {}
        }
    }

    // Self-test mode (used by the app's --selftest): no Wing connection.
    // Reads BATCH_SET lines from stdin and prints, for every parameter,
    // the exact bytes that would be sent to Wing ("path<TAB>hex"), so the
    // app can decode them and check the values that reach the console are
    // the values it meant to send.
    if encode_test {
        let stdin = std::io::stdin();
        let mut out = std::io::stdout();
        for line in stdin.lock().lines() {
            let Ok(l) = line else { break };
            let Some(params) = l.trim_end_matches(['\r', '\n']).strip_prefix("BATCH_SET ") else { continue };
            for param in params.split('\u{1f}') {
                if let Some((path, val)) = param.split_once('=') {
                    let hex = match encode_param(path.trim(), val) {
                        Some(b) => b.iter().map(|x| format!("{:02x}", x)).collect::<String>(),
                        None => "NONE".to_string(),
                    };
                    let _ = writeln!(out, "{}\t{}", path.trim(), hex);
                }
            }
        }
        let _ = out.flush();
        return Ok(());
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
    // Input SOURCE nodes (/io/in/GRP/N). Wing shows the source's name on a
    // channel strip whenever the channel's own name is empty, so the app
    // needs these to show the same names. Only paths the console schema
    // actually knows (name_to_id) are requested -- unknown group/number
    // combinations are skipped. Requested as whole nodes, exactly like
    // /ch/N below, so each one ends with a normal RequestEnd.
    // Groups and ranges verified against the real propmap.jsonl schema:
    // CRD/MOD go to 64 and USR to 56, so loop to 64 and let name_to_id
    // skip what doesn't exist. Internal '$' groups are deliberately left out.
    let io_groups = ["LCL", "AUX", "A", "B", "C", "SC", "USB", "CRD", "MOD", "PLAY", "AES", "USR", "OSC"];
    let mut io_paths: Vec<String> = Vec::new();
    for g in io_groups.iter() {
        for i in 1..=64 {
            let p = format!("/io/in/{}/{}", g, i);
            if WingConsole::name_to_id(&p).is_some() {
                io_paths.push(p);
            }
        }
    }
    eprintln!("[wingmon] SYNC: {} input source nodes", io_paths.len());

    // The Wing has 40 input channels + 8 Aux inputs (/aux/N). Plus the
    // parts of the console that Recall Scope -> Console Config covers:
    // audio config (/cfg), surface/preferences ($ctl/cfg), fader layers
    // ($ctl/layer), custom controls ($ctl/user) and the mute groups.
    let console_nodes = ["/cfg", "/$ctl/cfg", "/$ctl/layer", "/$ctl/user", "/$ctl/$globals"];
    let sync_paths: Vec<String> =
        (1..=40).map(|i| format!("/ch/{}", i))
        .chain((1..=8).map(|i|  format!("/aux/{}", i)))
        .chain((1..=16).map(|i| format!("/bus/{}", i)))
        .chain((1..=4).map(|i|  format!("/main/{}", i)))
        .chain((1..=8).map(|i|  format!("/mtx/{}", i)))
        .chain((1..=16).map(|i| format!("/dca/{}", i)))
        .chain((1..=16).map(|i| format!("/fx/{}", i)))
        .chain((1..=8).map(|i|  format!("/mgrp/{}", i)))
        .chain(console_nodes.iter().map(|p| p.to_string()))
        .chain(io_paths.into_iter())
        .filter(|p| WingConsole::name_to_id(p).is_some())
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
        // A read error used to be ignored here, so a connection that died
        // mid-sync left wingmon spinning in this loop forever (100% CPU,
        // never SYNC_COMPLETE, never reported as disconnected). Give up
        // after a few consecutive errors so the app sees the disconnect.
        let mut errors = 0u32;
        while pending > 0 {
            match event_wing.read() {
                Ok(WingResponse::RequestEnd)         => { pending -= 1; errors = 0; }
                Ok(WingResponse::NodeData(id, data)) => {
                    print_node(&tx_out, "DATA ", id, &value_string(&data));
                    total += 1;
                    errors = 0;
                }
                Ok(_) => { errors = 0; }
                Err(e) => {
                    errors += 1;
                    eprintln!("[wingmon] SYNC read error ({}): {}", errors, e);
                    if errors >= 3 {
                        eprintln!("[wingmon] SYNC failed - Wing not responding");
                        return Err(e);
                    }
                }
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
            // (No per-command log line here any more: during a fade this
            // logged 40 lines a second into the status bar and log file.)
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

        let mut pending: Option<String> = None;
        loop {
            let l = match pending.take() {
                Some(p) => p,
                None => match rx_cmd.recv() {
                    Ok(l) => l,
                    Err(_) => break,   // all senders dropped -- shutting down
                },
            };

            // Coalesce BATCH_SET: if another BATCH_SET is already waiting
            // right behind this one, skip straight to the newest instead
            // of processing this one first. Each fade tick's BATCH_SET
            // fully supersedes the previous tick's (same parameters, more
            // up-to-date values), so there is nothing lost by skipping a
            // stale one -- but there is a LOT to lose by not skipping it:
            // with no backpressure between Python's fixed 40fps tick timer
            // and however fast Wing can actually absorb commands, if Wing
            // ever falls behind for a sustained period (e.g. a long fade
            // with many simultaneously-fading parameters, while Wing is
            // also busy with real-time audio during a live show), this
            // queue would otherwise grow without bound and keep hammering
            // Wing with an ever-growing backlog of now-irrelevant
            // intermediate steps for minutes after the fade should have
            // finished -- exactly the kind of sustained overload that can
            // take down Wing's own network stack for every connected
            // client, not just this one, and not recoverable until this
            // process is killed. Coalescing means wingmon always converges
            // on the current target instead of drowning in stale history.
            let mut l = l;
            let mut coalesced = 0u32;
            if l.trim().starts_with("BATCH_SET ") {
                while let Ok(next) = rx_cmd.try_recv() {
                    if next.trim().starts_with("BATCH_SET ") {
                        l = next;   // supersede -- work with the newer one
                        coalesced += 1;
                    } else {
                        pending = Some(next);   // not coalescable -- preserve for next iteration, in order
                        break;
                    }
                }
            }
            if coalesced > 0 {
                eprintln!("[wingmon] BATCH_SET backlog: skipped {} stale tick(s), Wing may be falling behind", coalesced);
            }
            let trimmed = l.trim();
            let mut reconnect = false;

            if let Some(ref mut cmd) = cmd_opt {
                if let Some(params) = trimmed.strip_prefix("BATCH_SET ") {
                    // Small bursts (matching Wing Editor's wire behaviour),
                    // sent back-to-back with no artificial delay. TCP_NODELAY
                    // is enabled on this connection so each write goes out
                    // immediately rather than waiting on Nagle's algorithm.
                    const CHUNK: usize = 4;
                    // Parameters are separated by the ASCII unit separator
                    // (0x1f), not a comma, so names/texts containing a comma
                    // are recalled intact.
                    let all_params: Vec<&str> = params.split('\u{1f}').collect();
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
                    } else if all_params.len() > 50 {
                        // Logged for cue recalls only -- not for every fade
                        // tick (40 a second), which only flooded the log.
                        eprintln!("[wingmon] BATCH_SET sent: {} params, {} bytes in {} bursts, {}ms",
                            all_params.len(), sent_bytes, chunk_count, t0.elapsed().as_millis());
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
                print_node(&tx_out, "", id, &value_string(&data));
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

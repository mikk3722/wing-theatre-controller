"""
Patch libwing's WingConsole with:
1. write_raw()        — single TCP write for BATCH_SET (Wing Editor protocol)
2. set_read_timeout() — override libwing's short default timeout
"""
import re, sys

path = 'libwing/src/console.rs'
src = open(path).read()

if 'write_raw' in src:
    print('Already patched — skipping')
    sys.exit(0)

methods = '''
    /// Send raw bytes in one TCP write — matches Wing Editor's wire protocol.
    pub fn write_raw(&mut self, data: &[u8]) -> crate::Result<()> {
        use std::io::Write;
        self.wsock.clone().lock().unwrap().write_all(data)?;
        Ok(())
    }

    /// Override the read timeout on the underlying socket.
    /// Pass a large value (e.g. 86400) to effectively disable timeouts,
    /// preventing spurious OS 10060 errors on Windows.
    pub fn set_read_timeout_secs(&self, secs: u64) {
        use std::time::Duration;
        let dur = if secs == 0 { None } else { Some(Duration::from_secs(secs)) };
        let _ = self.wsock.clone().lock().unwrap().set_read_timeout(dur);
    }
'''

# Insert before closing brace of impl WingConsole
impl_start = src.find('impl WingConsole')
if impl_start < 0:
    print('ERROR: impl WingConsole not found'); sys.exit(1)

brace_open = src.find('{', impl_start)
depth = 0; pos = brace_open
while pos < len(src):
    if src[pos] == '{': depth += 1
    elif src[pos] == '}':
        depth -= 1
        if depth == 0: insert_at = pos; break
    pos += 1

open(path, 'w').write(src[:insert_at] + methods + src[insert_at:])
print('write_raw + set_read_timeout_secs injected into impl WingConsole')

"""
Patch libwing's WingConsole with:
1. write_raw()          - single TCP write for BATCH_SET (Wing Editor protocol)
2. set_read_timeout_secs() - override libwing's short default read timeout
3. set_nodelay()        - disable Nagle's algorithm for fast small writes
"""
import re, sys

path = 'libwing/src/console.rs'
src = open(path, encoding='utf-8').read()

if 'write_raw' in src:
    print('Already patched - skipping')
    sys.exit(0)

methods = '''
    /// Send raw bytes in one TCP write - matches Wing Editor's wire protocol.
    pub fn write_raw(&mut self, data: &[u8]) -> crate::Result<()> {
        use std::io::Write;
        self.wsock.clone().lock().unwrap().write_all(data)?;
        Ok(())
    }

    /// Override the read timeout on the underlying socket.
    /// Pass a large value (e.g. 86400) to effectively disable timeouts.
    pub fn set_read_timeout_secs(&self, secs: u64) {
        use std::time::Duration;
        let dur = if secs == 0 { None } else { Some(Duration::from_secs(secs)) };
        let _ = self.wsock.clone().lock().unwrap().set_read_timeout(dur);
    }

    /// Disable Nagle's algorithm (TCP_NODELAY) so small writes are sent
    /// immediately instead of being buffered waiting for more data or an ACK.
    pub fn set_nodelay(&self) {
        let _ = self.wsock.clone().lock().unwrap().set_nodelay(true);
    }
'''

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

open(path, 'w', encoding='utf-8').write(src[:insert_at] + methods + src[insert_at:])
print('write_raw + set_read_timeout_secs + set_nodelay injected into impl WingConsole')

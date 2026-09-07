"""
Patch libwing's WingConsole with:
1. write_raw()    - single TCP write for BATCH_SET (Wing Editor protocol)
2. set_nodelay()  - disable Nagle's algorithm for fast small writes
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

    /// Disable Nagle's algorithm (TCP_NODELAY) so small writes are sent
    /// immediately instead of being buffered waiting for more data or an ACK.
    /// Critical for fast BATCH_SET bursts of many small writes.
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
print('write_raw + set_nodelay injected into impl WingConsole')

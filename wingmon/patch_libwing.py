"""
Inject write_raw() into libwing's WingConsole so wingmon can send
all BATCH_SET parameters in ONE TCP write — matching Wing Editor's
wire protocol exactly.
"""
import re, sys

path = 'libwing/src/console.rs'
src = open(path).read()

method = '''
    /// Send raw bytes directly to Wing's TCP socket.
    /// Used by BATCH_SET to send all parameters in a single write,
    /// matching Wing Editor's binary protocol.
    pub fn write_raw(&mut self, data: &[u8]) -> crate::Result<()> {
        use std::io::Write;
        self.wsock.clone().lock().unwrap().write_all(data)?;
        Ok(())
    }
'''

# Insert before the last closing brace in the file
if 'write_raw' in src:
    print('write_raw already present — skipping')
    sys.exit(0)

# Find last } and insert method before it
last_brace = src.rfind('\n}')
if last_brace < 0:
    print('ERROR: could not find closing brace in console.rs')
    sys.exit(1)

patched = src[:last_brace] + method + src[last_brace:]
open(path, 'w').write(patched)
print(f'write_raw injected into {path}')

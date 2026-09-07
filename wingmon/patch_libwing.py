"""
Inject write_raw() into libwing's WingConsole impl block.
Lets BATCH_SET send all params in ONE TCP write — Wing Editor protocol.
"""
import re, sys

path = 'libwing/src/console.rs'
src = open(path).read()

if 'write_raw' in src:
    print('Already patched — skipping')
    sys.exit(0)

method = '''
    pub fn write_raw(&mut self, data: &[u8]) -> crate::Result<()> {
        use std::io::Write;
        self.wsock.clone().lock().unwrap().write_all(data)?;
        Ok(())
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

open(path, 'w').write(src[:insert_at] + method + src[insert_at:])
print('write_raw injected into impl WingConsole')

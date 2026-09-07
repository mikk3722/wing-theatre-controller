"""
Inject write_raw() into libwing's WingConsole impl block.
Inserts before the FIRST closing brace that ends the main impl block.
"""
import re, sys

path = 'libwing/src/console.rs'
src = open(path).read()

if 'write_raw' in src:
    print('write_raw already present — skipping')
    sys.exit(0)

method = '''
    pub fn write_raw(&mut self, data: &[u8]) -> crate::Result<()> {
        use std::io::Write;
        self.wsock.clone().lock().unwrap().write_all(data)?;
        Ok(())
    }
'''

# Find "impl WingConsole" block and insert before its closing brace.
# Strategy: find "impl WingConsole {", then find the matching closing brace.
impl_start = src.find('impl WingConsole')
if impl_start < 0:
    print('ERROR: impl WingConsole not found in console.rs')
    print('Contents:', src[:500])
    sys.exit(1)

# Find the opening brace of the impl block
brace_open = src.find('{', impl_start)
if brace_open < 0:
    print('ERROR: no opening brace after impl WingConsole')
    sys.exit(1)

# Walk forward to find the matching closing brace
depth = 0
pos = brace_open
while pos < len(src):
    if src[pos] == '{':
        depth += 1
    elif src[pos] == '}':
        depth -= 1
        if depth == 0:
            # This is the closing brace of impl WingConsole
            insert_at = pos
            break
    pos += 1
else:
    print('ERROR: could not find closing brace of impl WingConsole')
    sys.exit(1)

patched = src[:insert_at] + method + src[insert_at:]
open(path, 'w').write(patched)
print(f'write_raw injected into impl WingConsole at position {insert_at}')

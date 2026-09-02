# Wing Theatre Controller

Controls Wing Theatre Controller — show-control for Behringer Wing.

## Setup
1. In Wing Theatre → OSC Settings → enable TCP Remote Control
2. Note the port (default 9000)
3. Enter the IP and port here

## Variables
- `$(wingtheatre:current_cue_num)` / `current_cue_name`
- `$(wingtheatre:next_cue_num)` / `next_cue_name`
- `$(wingtheatre:autoupdate)` — true/false
- `$(wingtheatre:wing_connected)` — true/false
- `$(wingtheatre:cue_count)` / `fading`

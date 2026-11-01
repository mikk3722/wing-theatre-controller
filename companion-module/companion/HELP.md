# Wing Theatre Controller

Controls Wing Theatre Controller — show-control for Behringer Wing.

## Setup
1. In Wing Theatre Controller → OSC Settings → switch on **Companion / TCP Remote Control**
2. Note the port (default **9001**)
3. Enter the IP of the computer running Wing Theatre Controller and the port here

Up to 4 Companions can be connected at the same time. A 5th connection is refused
(the connection status shows "server full").

## Actions
GO, Next GO, Previous GO, GO specific cue, Next / Previous (no GO),
Auto Update ON / OFF / Toggle, Add Snapshot, **Cancel fade**, Request full state update

## Variables
- `$(wingtheatre:current_cue_num)` / `current_cue_name`
- `$(wingtheatre:next_cue_num)` / `next_cue_name`
- `$(wingtheatre:selected_cue_num)` / `selected_cue_name`
- `$(wingtheatre:autoupdate)` — true/false
- `$(wingtheatre:wing_connected)` — true/false
- `$(wingtheatre:cue_count)`
- `$(wingtheatre:fading)` — true/false
- `$(wingtheatre:fade_remaining)` — seconds left of the newest fade

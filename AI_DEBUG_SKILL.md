# AI-Driven Serial Servo Debugging Skill

> Let AI do the grunt work: checksums, frame construction, baud scanning, register lookups.

## Core Principle

**Human makes decisions, AI does the work.**

Traditional servo debugging: you read manuals, calculate hex checksums, try baud rates one by one, wonder why there's no response.

AI-driven debugging: you say "find the servo", "set ID to 2", "calibrate" — AI handles the protocol.

## When to Use

- Setting up a new servo-based robot (LeRobot, Koch, So100)
- Adding/replacing a servo in an existing system
- Debugging "no response" / "wrong position" issues
- Tuning PID or calibration offsets

## Phase 1: Reconnaissance (AI does this)

Let AI scan and report:

```
You: "scan the servo bus"
AI:  Finds /dev/cu.usbmodemXXXX, tries baud rates, finds ID=1 @ 1Mbps
```

**AI handles:**
- Port detection (`ls /dev/cu.*` → filter usbmodem/usbserial)
- Baud rate scanning (try 1M, 500K, 250K, 115200, 9600 with Ping)
- Protocol frame construction (`FF FF ID LEN INST PARAM CHK`)
- Checksum calculation (`~sum & 0xFF`)
- Response parsing (verify frame header, ID, error code, checksum)

**You just read the result.**

## Phase 2: Identify & Resolve Conflicts

Symptom: two servos, both default ID=1, bus conflict.

```
You: "the second servo needs a unique ID, set it to 2"
AI:  Unlocks EPROM → writes ID=2 → locks → verifies
```

**AI knows the sequence:**
1. `write_byte(old_id, Lock=55, 0)` — unlock
2. `write_byte(old_id, ID=5, new_id)` — change ID
3. `write_byte(new_id, Lock=55, 1)` — lock with NEW id

**Common trap:** Locking with old ID → new ID doesn't stick.

## Phase 3: Calibration

Symptom: need to set mechanical zero point.

```
You: "calibrate servo 2"
AI:  Reads current position → sends calibrate(128) → enables torque → verifies
```

**AI knows the "secret":**
- HLS/SMS_STS calibration = write **128** to Torque Enable register (address 40)
- NOT writing to the offset register (address 31)
- Offset register updates automatically after calibration

**Common trap:** Writing offset directly doesn't work. Must use 128 trick.

## Phase 4: Verification

```
You: "show me servo 2 status"
AI:  position=2048, speed=0, temp=27°C, voltage=5.3V, torque=on
```

## Quick Reference

| Task | Command |
|------|---------|
| Scan bus | `python scan.py --port /dev/cu.usbmodemXXXX` |
| Calibrate | `python calibrate.py --port ... --id N` |
| Change ID | `python set_id.py --port ... --old 1 --new 2` |
| Monitor | `python monitor.py --port ... --id N` |
| Status | `python ft_servo.py status --port ... --id N` |

## Lessons from Real Debugging

### 1. Power matters
USB alone cannot drive a servo motor. Must have external 5-7.4V power. CH343P provides signal only.

### 2. Baud rate is usually 1Mbps
Feetech servos default to 1Mbps. If that fails, try 115200 (some older models).

### 3. Default ID is always 1
Every servo ships with ID=1. Before connecting a second servo, change its ID.

### 4. Calibrate AFTER changing ID
Calibration stores offset in servo's EPROM. If you change ID after calibrating, offset may reset.

### 5. Locking EPROM is final
After `Lock=55 → 1`, the servo won't accept writes until unlocked. This protects against accidental changes but can confuse debugging.

### 6. Two servos on same bus = half-duplex collision
Feetech servos share one signal wire for TX/RX. If both try to respond simultaneously, data corrupts. This is normal — just ensure IDs are unique.

## Integration with AI Agent

Tell the AI:

```
Port: /dev/cu.usbmodem5B790502931
Task: I have 2 servos. Set IDs to 1 and 2, calibrate both.
```

AI will:
1. Scan → find both at ID=1 (conflict)
2. Change second to ID=2
3. Calibrate ID=1 (write 128 to reg 40)
4. Calibrate ID=2
5. Verify both respond

Total time: ~30 seconds. No manual hex, no checksum errors.

## Files

- `ft_servo.py` — core library
- `scan.py`, `calibrate.py`, `set_id.py`, `monitor.py` — CLI tools
- `memory_table.md` — register reference

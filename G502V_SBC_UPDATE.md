# G502V SBC Update Notes

Use these notes when preparing the public G502V repo for Streamer Board & Console integration.

Recommended checks:

```bash
cd /path/to/Streamer_Board_Console
./tools/g502v_adapter_safe_cycle.sh
./tools/g502v_yaw_direction_safe_cycle.sh
./tools/sbc_adapter_doctor.py
```

Runtime control files such as `sbc_control.json` and `g502v.control.json` should stay local and ignored by Git.

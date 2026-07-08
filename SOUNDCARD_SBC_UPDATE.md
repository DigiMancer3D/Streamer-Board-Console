# Soundcard SBC Update Notes

Use these notes when preparing the public Soundcard repo for Streamer Board & Console integration.

Recommended checks:

```bash
cd /path/to/Streamer_Board_Console
./tools/soundcard_adapter_safe_cycle.sh
./tools/sbc_adapter_doctor.py
```

Runtime control files such as `sbc_control.json` and `soundcard.control.json` should stay local and ignored by Git.

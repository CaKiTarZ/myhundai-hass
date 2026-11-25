# Hyundai Tucson Charge Fix (Home Assistant)

A Home Assistant custom integration designed to fix the Hyundai Bluelink app bug where scheduled/off-peak charging randomly re-enables itself, and to reliably enforce your charging schedule:

- **Weekdays (Mon–Fri):** `00:00` – `08:00` (`Europe/Madrid` by default, configurable)
- **Weekends (Sat–Sun):** All day (`00:00` – `24:00`, configurable)
- **Rogue schedule auto-fix:** Automatically detects when the Hyundai app re-enables the in-car charging schedule and disables it via Bluelink.
- **Exact boundary triggers:** Schedules an exact Home Assistant callback at `00:00` and `08:00` so charging starts/stops on time instead of waiting for the next polling cycle.

## Installation

### Option 1: HACS (Custom Repository)
1. Open **HACS** in Home Assistant → **Integrations** → **⋮ (top right)** → **Custom repositories**.
2. Add this repository URL with category **Integration**.
3. Install **Hyundai Tucson Charge Fix** and restart Home Assistant.

### Option 2: Manual
1. Copy `custom_components/hyundai_tucson_charge_fix` into your Home Assistant `/config/custom_components/` directory.
2. Restart Home Assistant.

## Configuration
1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Hyundai Tucson Charge Fix**.
3. Enter your Hyundai Bluelink email, password, PIN (needed for remote start/stop), and select **Europe (Standard Bluelink)** (or **Europe (CCI / GSPA)** if your account uses the newer EU platform).
4. Keep the defaults (`00:00` to `08:00`, weekend all day, `Europe/Madrid`) or customize them anytime via **Configure**.

## Entities Provided
- `binary_sensor.*_charging_window_active` — `ON` during allowed charging hours.
- `binary_sensor.*_plugged_in` — `ON` when the cable is connected.
- `binary_sensor.*_charging` — `ON` when actively charging.
- `binary_sensor.*_in_car_schedule_enabled` — `ON` (problem) if the Hyundai app randomly turned the in-car schedule back on.
- `sensor.*_battery_level` — Vehicle battery percentage.
- `sensor.*_last_action` — Last enforcement action taken and any error details.
- `sensor.*_next_window_change` — Timestamp of the next schedule transition.
- `switch.*_auto_enforce_schedule` — Master toggle to pause/resume automatic enforcement.
- `switch.*_charging` — Manual override to start/stop charging immediately.
- `button.*_force_refresh` — Wakes the car for a live Bluelink refresh.
- `button.*_enforce_schedule_now` — Immediately polls and enforces the schedule.

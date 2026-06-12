#!/usr/bin/env python3
"""
Validation Spike — Two-Area Frequency ODE Sanity Check.

Injects a step disturbance into the east area and plots the resulting
frequency deviation curves. This is the Phase 1 pass/fail gate:
the curves must show a believable dip-and-recovery shape.

Expected behavior:
    1. East frequency dips after load increase
    2. West frequency also dips slightly (coupled via tie-line)
    3. Both frequencies oscillate and recover toward nominal
    4. Governor response provides primary frequency control
    5. No numerical blow-up over the simulation window

Usage:
    python scripts/run_validation_spike.py
"""

import sys
import os

# Add project root to path so we can import src modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import matplotlib.pyplot as plt
from src.physics.frequency_model import (
    FrequencyModel,
    SystemState,
    Disturbance,
    TwoAreaParams,
    AreaParams,
)


def run_step_disturbance():
    """Scenario 1: Step load increase in east area."""
    print("=" * 60)
    print("VALIDATION SPIKE -- Step Disturbance Test")
    print("=" * 60)

    model = FrequencyModel()
    state = SystemState()

    # Inject 10% step load increase in east area (generation loss)
    disturbance = Disturbance(east_pu=-0.10, west_pu=0.0)

    print(f"\nDisturbance: {disturbance.east_pu} pu in east, {disturbance.west_pu} pu in west")
    print(f"Parameters: H_east={model.params.east.inertia_h}s, "
          f"H_west={model.params.west.inertia_h}s")
    print(f"Damping: D_east={model.params.east.damping_d}, "
          f"D_west={model.params.west.damping_d}")
    print(f"Tie-line: T12={model.params.sync_coeff_t12}")
    print(f"Governor: R_east={model.params.east.governor_r}, "
          f"R_west={model.params.west.governor_r}")

    # Simulate 60 seconds
    result = model.simulate(state, disturbance, duration=60.0, dt=0.05)

    print(f"\n--- Results ---")
    print(f"Max deviation east: {result.max_deviation_east_hz():.4f} Hz")
    print(f"Max deviation west: {result.max_deviation_west_hz():.4f} Hz")

    recovery_east = result.recovery_time("east", threshold_pu=0.001)
    recovery_west = result.recovery_time("west", threshold_pu=0.001)
    print(f"Recovery time east (to 0.1%): {recovery_east:.2f}s" if recovery_east else
          "Recovery time east: NOT SETTLED")
    print(f"Recovery time west (to 0.1%): {recovery_west:.2f}s" if recovery_west else
          "Recovery time west: NOT SETTLED")

    return result


def run_symmetric_disturbance():
    """Scenario 2: Simultaneous disturbance in both areas."""
    print("\n" + "=" * 60)
    print("VALIDATION SPIKE -- Symmetric Disturbance Test")
    print("=" * 60)

    model = FrequencyModel()
    state = SystemState()

    disturbance = Disturbance(east_pu=-0.05, west_pu=-0.08)
    print(f"\nDisturbance: {disturbance.east_pu} pu east, {disturbance.west_pu} pu west")

    result = model.simulate(state, disturbance, duration=60.0, dt=0.05)

    print(f"Max deviation east: {result.max_deviation_east_hz():.4f} Hz")
    print(f"Max deviation west: {result.max_deviation_west_hz():.4f} Hz")

    return result


def run_no_governor():
    """Scenario 3: Disturbance without governor response (worst case)."""
    print("\n" + "=" * 60)
    print("VALIDATION SPIKE -- No Governor Response Test")
    print("=" * 60)

    params = TwoAreaParams(
        east=AreaParams(name="east", nominal_freq_hz=50.0, inertia_h=5.0,
                        damping_d=1.0, governor_enabled=False),
        west=AreaParams(name="west", nominal_freq_hz=60.0, inertia_h=6.0,
                        damping_d=1.2, governor_enabled=False),
    )
    model = FrequencyModel(params)
    state = SystemState()

    disturbance = Disturbance(east_pu=-0.10)
    print(f"\nDisturbance: {disturbance.east_pu} pu in east (NO governor)")

    result = model.simulate(state, disturbance, duration=60.0, dt=0.05)

    print(f"Max deviation east: {result.max_deviation_east_hz():.4f} Hz")
    print(f"Max deviation west: {result.max_deviation_west_hz():.4f} Hz")

    return result


def plot_results(result_step, result_sym, result_nogov):
    """Generate validation plots."""
    fig, axes = plt.subplots(3, 2, figsize=(14, 12))
    fig.suptitle("FreqBridge — Validation Spike: Two-Area Swing Equation",
                 fontsize=14, fontweight="bold")

    # --- Scenario 1: Step disturbance ---
    ax = axes[0, 0]
    ax.plot(result_step.times, result_step.freq_east_hz(), "b-", label="East (50 Hz)", linewidth=1.5)
    ax.axhline(y=50.0, color="b", linestyle="--", alpha=0.3)
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title("Scenario 1: East Step Disturbance (-0.1 pu)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    ax.plot(result_step.times, result_step.freq_west_hz(), "r-", label="West (60 Hz)", linewidth=1.5)
    ax.axhline(y=60.0, color="r", linestyle="--", alpha=0.3)
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title("Scenario 1: West Response (Coupled)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # --- Scenario 2: Symmetric disturbance ---
    ax = axes[1, 0]
    ax.plot(result_sym.times, result_sym.freq_east_hz(), "b-", label="East (50 Hz)", linewidth=1.5)
    ax.plot(result_sym.times, result_sym.freq_west_hz(), "r-", label="West (60 Hz)", linewidth=1.5)
    ax.axhline(y=50.0, color="b", linestyle="--", alpha=0.3)
    ax.axhline(y=60.0, color="r", linestyle="--", alpha=0.3)
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title("Scenario 2: Both Areas Disturbed (-0.05/-0.08 pu)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[1, 1]
    ax.plot(result_sym.times, result_sym.delta_angle, "g-", linewidth=1.5)
    ax.set_ylabel("d_delta (rad)")
    ax.set_title("Scenario 2: Rotor Angle Difference")
    ax.grid(True, alpha=0.3)

    # --- Scenario 3: No governor ---
    ax = axes[2, 0]
    ax.plot(result_nogov.times, result_nogov.freq_east_hz(), "b-", label="East (no gov)", linewidth=1.5)
    ax.plot(result_step.times, result_step.freq_east_hz(), "b--", label="East (with gov)", linewidth=1.0, alpha=0.6)
    ax.axhline(y=50.0, color="b", linestyle=":", alpha=0.3)
    ax.set_ylabel("Frequency (Hz)")
    ax.set_xlabel("Time (s)")
    ax.set_title("Scenario 3: Governor vs No Governor (East)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[2, 1]
    ax.plot(result_nogov.times, result_nogov.freq_west_hz(), "r-", label="West (no gov)", linewidth=1.5)
    ax.plot(result_step.times, result_step.freq_west_hz(), "r--", label="West (with gov)", linewidth=1.0, alpha=0.6)
    ax.axhline(y=60.0, color="r", linestyle=":", alpha=0.3)
    ax.set_ylabel("Frequency (Hz)")
    ax.set_xlabel("Time (s)")
    ax.set_title("Scenario 3: Governor vs No Governor (West)")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    # Save to data/
    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "validation_spike.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"\nPlot saved to: {output_path}")

    plt.show()


def main():
    result_step = run_step_disturbance()
    result_sym = run_symmetric_disturbance()
    result_nogov = run_no_governor()

    # --- PASS/FAIL GATE ---
    print("\n" + "=" * 60)
    print("PASS / FAIL GATE")
    print("=" * 60)

    checks = []

    # Check 1: East frequency should dip (negative deviation)
    min_east = np.min(result_step.delta_f_east)
    check1 = min_east < -0.001
    checks.append(check1)
    print(f"[{'PASS' if check1 else 'FAIL'}] East frequency dips after disturbance "
          f"(min delta_f = {min_east:.6f} pu)")

    # Check 2: Max deviation should be < 2 Hz (physically reasonable)
    max_dev = result_step.max_deviation_east_hz()
    check2 = max_dev < 2.0
    checks.append(check2)
    print(f"[{'PASS' if check2 else 'FAIL'}] Max deviation < 2 Hz "
          f"(actual: {max_dev:.4f} Hz)")

    # Check 3: Frequency should recover (settle toward 0)
    final_dev = abs(result_step.delta_f_east[-1])
    check3 = final_dev < 0.01  # Within 1% at end of 60s
    checks.append(check3)
    print(f"[{'PASS' if check3 else 'FAIL'}] Frequency settles (final |delta_f| = {final_dev:.6f} pu)")

    # Check 4: No numerical blow-up
    check4 = np.all(np.isfinite(result_step.delta_f_east)) and np.all(np.isfinite(result_step.delta_f_west))
    checks.append(check4)
    print(f"[{'PASS' if check4 else 'FAIL'}] No numerical blow-up")

    # Check 5: Governor should improve recovery vs no-governor
    final_gov = abs(result_step.delta_f_east[-1])
    final_nogov = abs(result_nogov.delta_f_east[-1])
    check5 = final_gov < final_nogov
    checks.append(check5)
    print(f"[{'PASS' if check5 else 'FAIL'}] Governor improves recovery "
          f"(with: {final_gov:.6f}, without: {final_nogov:.6f})")

    # Check 6: West area should also be affected (coupling works)
    max_dev_west = result_step.max_deviation_west_hz()
    check6 = max_dev_west > 0.001
    checks.append(check6)
    print(f"[{'PASS' if check6 else 'FAIL'}] West area responds to east disturbance "
          f"(max delta_f_west = {max_dev_west:.4f} Hz)")

    print(f"\n{'=' * 60}")
    all_pass = all(checks)
    print(f"OVERALL: {'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED'}")
    print(f"{'=' * 60}")

    if all_pass:
        print("\n-> Phase 1 gate PASSED. Safe to proceed to Phase 2.")
    else:
        print("\n-> Phase 1 gate FAILED. Fix ODE parameters before proceeding.")

    plot_results(result_step, result_sym, result_nogov)

    return all_pass


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

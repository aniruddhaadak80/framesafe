/**
 * `flash-strict` — a stricter flash threshold for review passes.
 *
 * The engine's shipping rule is three flash reversals per second (WCAG 2.3.1 / BT.2020).
 * Reviewing a clip at two per second gives an editor margin, so a clip that only just
 * passes shipping still looks uncomfortable in a small preview window.
 *
 * The plugin owns the threshold only. The measurement itself stays in the engine, because
 * a plugin that re-measured frames would be a second implementation of the audit — and two
 * implementations of a safety rule is exactly how a safety rule stops being one.
 */

export const manifest = {
  name: 'flash-strict',
  version: '0.1.0',
}

/** Flash reversals per second this plugin considers acceptable. */
export const MAX_FLASHES_PER_SECOND = 2

/** WCAG 2.3.1 / ITU-R BT.2020 general flash threshold, as a fraction of relative luminance. */
export const GENERAL_FLASH_DELTA = 0.1

/**
 * Evaluate a committed flash audit under this plugin's threshold.
 *
 * @param {{ maxFlashesInWindow: number }} audit the shipping audit from the manifest
 * @returns {{ passed: boolean, ceiling: number, observed: number }}
 */
export function evaluate(audit) {
  return {
    passed: audit.maxFlashesInWindow <= MAX_FLASHES_PER_SECOND,
    ceiling: MAX_FLASHES_PER_SECOND,
    observed: audit.maxFlashesInWindow,
  }
}

export function describe() {
  return {
    plugin: manifest.name,
    capability: 'audit.flash-strict',
    maxFlashesPerSecond: MAX_FLASHES_PER_SECOND,
    generalFlashDelta: GENERAL_FLASH_DELTA,
  }
}

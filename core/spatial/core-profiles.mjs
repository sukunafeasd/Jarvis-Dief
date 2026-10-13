export const CORE_PROFILES = Object.freeze({
  booting: { speed: 0.7, energy: 0.25, luminosity: 0.55 },
  idle: { speed: 0.26, energy: 0.05, luminosity: 0.62 },
  awaiting_response: { speed: 0.18, energy: 0.025, luminosity: 0.68 },
  wake_detected: { speed: 1.2, energy: 0.8, luminosity: 1 },
  listening: { speed: 0.46, energy: 0.2, luminosity: 0.8 },
  transcribing: { speed: 0.78, energy: 0.4, luminosity: 0.9 },
  thinking: { speed: 1.3, energy: 0.5, luminosity: 0.86 },
  responding: { speed: 0.8, energy: 0.6, luminosity: 0.92 },
  speaking: { speed: 0.55, energy: 0.2, luminosity: 0.9 },
  executing: { speed: 1, energy: 0.55, luminosity: 0.84 },
  success: { speed: 0.4, energy: 0.65, luminosity: 1 },
  warning: { speed: 0.48, energy: 0.3, luminosity: 0.8, color: "#eebd75" },
  critical: { speed: 0.6, energy: 0.5, luminosity: 0.87, color: "#ed7c81" },
  error: { speed: 0.18, energy: 0.1, luminosity: 0.65, color: "#ed7c81" },
  offline: { speed: 0.13, energy: 0.03, luminosity: 0.35, color: "#70848d" },
  sleeping: { speed: 0.12, energy: 0.015, luminosity: 0.3 },
});
export function coreProfile(state) {
  return (
    CORE_PROFILES[
      { working: "thinking", received: "transcribing" }[state] || state
    ] || CORE_PROFILES.idle
  );
}

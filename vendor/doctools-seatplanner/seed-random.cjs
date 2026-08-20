// Deterministic Math.random preload for the unmodified DOC_TOOLS Seat Planner.
let state = Number.parseInt(process.env.SEATPLANNER_SEED || '210', 10) >>> 0;
Math.random = function () {
  state = (state * 1664525 + 1013904223) >>> 0;
  return state / 4294967296;
};

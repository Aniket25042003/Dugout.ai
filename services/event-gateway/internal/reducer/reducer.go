// File: services/event-gateway/internal/reducer/reducer.go
// Layer: Domain Logic — Baseball Game State Reducer
// Purpose: Applies immutable GameEvent payloads to GameState so the gateway can
// replay event history into current scoreboard, count, bases, and active players.
// Dependencies: generated Go contracts and protobuf cloning.
package reducer

import (
	"github.com/Aniket25042003/Dugout/packages/contracts/go/dugout/v1"
	"google.golang.org/protobuf/proto"
)

// Reduce applies a GameEvent to the current GameState and returns the new GameState.
// It clones the state before modifying it to ensure pure functionality.
func Reduce(state *dugoutv1.GameState, event *dugoutv1.GameEvent) *dugoutv1.GameState {
	if state == nil {
		return nil
	}
	if event == nil {
		return state
	}

	// 1. Clone state to prevent side effects
	newState := proto.Clone(state).(*dugoutv1.GameState)

	// 2. Update common event metadata
	newState.LastEventId = event.EventId
	newState.UpdatedAt = event.OccurredAt

	// 3. Process the event payload
	switch payload := event.Payload.(type) {
	case *dugoutv1.GameEvent_PitchResult:
		applyPitchResult(newState, payload.PitchResult)

	case *dugoutv1.GameEvent_PlayOutcome:
		applyPlayOutcome(newState, payload.PlayOutcome)

	case *dugoutv1.GameEvent_InningTransition:
		applyInningTransition(newState, payload.InningTransition)

	case *dugoutv1.GameEvent_Substitution:
		applySubstitution(newState, payload.Substitution)

	case *dugoutv1.GameEvent_ClockControl:
		applyClockControl(newState, payload.ClockControl)

	case *dugoutv1.GameEvent_Correction:
		applyCorrection(newState, payload.Correction)
	}

	return newState
}

func applyPitchResult(state *dugoutv1.GameState, pitch *dugoutv1.PitchResultPayload) {
	// Pitch results maintain count and active matchup context between play outcomes.
	if pitch == nil {
		return
	}

	// Update pitcher/batter if provided
	if pitch.PitcherId != "" {
		state.ActivePitcherId = pitch.PitcherId
	}
	if pitch.BatterId != "" {
		state.ActiveBatterId = pitch.BatterId
	}

	switch pitch.Result {
	case dugoutv1.PitchResultType_PITCH_RESULT_TYPE_BALL:
		state.Balls++
		if state.Balls >= 4 {
			// Walk
			advanceRunnersOnWalk(state, state.ActiveBatterId)
			resetCount(state)
			advanceBattingIndex(state)
		}

	case dugoutv1.PitchResultType_PITCH_RESULT_TYPE_STRIKE_LOOKING,
		dugoutv1.PitchResultType_PITCH_RESULT_TYPE_STRIKE_SWINGING:
		state.Strikes++
		if state.Strikes >= 3 {
			// Strikeout (Out)
			state.Outs++
			resetCount(state)
			advanceBattingIndex(state)
			checkHalfInningEnd(state)
		}

	case dugoutv1.PitchResultType_PITCH_RESULT_TYPE_FOUL:
		// Foul is a strike unless there are already 2 strikes
		if state.Strikes < 2 {
			state.Strikes++
		}

	case dugoutv1.PitchResultType_PITCH_RESULT_TYPE_HIT_BY_PITCH:
		// Hit by pitch is treated as a walk
		advanceRunnersOnWalk(state, state.ActiveBatterId)
		resetCount(state)
		advanceBattingIndex(state)

	case dugoutv1.PitchResultType_PITCH_RESULT_TYPE_PUT_IN_PLAY:
		// Count resets, outcome details will come in subsequent play outcome event
		resetCount(state)
	}
}

func applyPlayOutcome(state *dugoutv1.GameState, outcome *dugoutv1.PlayOutcomePayload) {
	// Play outcomes finalize balls in play: score, outs, base movement, and order.
	if outcome == nil {
		return
	}

	resetCount(state)

	// Apply explicitly recorded outs and runs
	state.Outs += outcome.OutsRecorded
	if outcome.RunsScored > 0 {
		addRuns(state, outcome.RunsScored)
	}

	if state.Outs >= 3 {
		resetCount(state)
		clearBases(state)
		transitionHalfInning(state)
		return
	}

	// Map bases advancement for standard hits
	switch outcome.Type {
	case dugoutv1.PlayOutcomeType_PLAY_OUTCOME_TYPE_SINGLE:
		// Move runner on 3rd home
		if state.RunnerOnThird {
			addRuns(state, 1)
		}
		// Move runner on 2nd to 3rd
		state.RunnerOnThird = state.RunnerOnSecond
		state.RunnerOnThirdPlayerId = state.RunnerOnSecondPlayerId
		// Move runner on 1st to 2nd
		state.RunnerOnSecond = state.RunnerOnFirst
		state.RunnerOnSecondPlayerId = state.RunnerOnFirstPlayerId
		// Batter to 1st
		state.RunnerOnFirst = true
		state.RunnerOnFirstPlayerId = outcome.BatterId
		advanceBattingIndex(state)

	case dugoutv1.PlayOutcomeType_PLAY_OUTCOME_TYPE_DOUBLE:
		// Runners on 3rd and 2nd score
		if state.RunnerOnThird {
			addRuns(state, 1)
		}
		if state.RunnerOnSecond {
			addRuns(state, 1)
		}
		// Runner on 1st to 3rd
		state.RunnerOnThird = state.RunnerOnFirst
		state.RunnerOnThirdPlayerId = state.RunnerOnFirstPlayerId
		// Runner on 2nd is empty
		state.RunnerOnSecond = true
		state.RunnerOnSecondPlayerId = outcome.BatterId
		// Runner on 1st is empty
		state.RunnerOnFirst = false
		state.RunnerOnFirstPlayerId = ""
		advanceBattingIndex(state)

	case dugoutv1.PlayOutcomeType_PLAY_OUTCOME_TYPE_TRIPLE:
		// All runners score
		if state.RunnerOnThird {
			addRuns(state, 1)
		}
		if state.RunnerOnSecond {
			addRuns(state, 1)
		}
		if state.RunnerOnFirst {
			addRuns(state, 1)
		}
		// Clear 1st and 2nd, batter to 3rd
		state.RunnerOnFirst = false
		state.RunnerOnFirstPlayerId = ""
		state.RunnerOnSecond = false
		state.RunnerOnSecondPlayerId = ""
		state.RunnerOnThird = true
		state.RunnerOnThirdPlayerId = outcome.BatterId
		advanceBattingIndex(state)

	case dugoutv1.PlayOutcomeType_PLAY_OUTCOME_TYPE_HOME_RUN:
		// Everyone scores
		scored := 1 // Batter
		if state.RunnerOnThird {
			scored++
		}
		if state.RunnerOnSecond {
			scored++
		}
		if state.RunnerOnFirst {
			scored++
		}
		addRuns(state, int32(scored))
		clearBases(state)
		advanceBattingIndex(state)

	case dugoutv1.PlayOutcomeType_PLAY_OUTCOME_TYPE_WALK:
		advanceRunnersOnWalk(state, outcome.BatterId)
		advanceBattingIndex(state)

	case dugoutv1.PlayOutcomeType_PLAY_OUTCOME_TYPE_OUT:
		// Simple batter out (strikeout handled in pitch result, but this handles flyout/groundout)
		advanceBattingIndex(state)
	}
}

func applyInningTransition(state *dugoutv1.GameState, transition *dugoutv1.InningTransitionPayload) {
	// Explicit inning transitions override inferred half-inning state from outs.
	if transition == nil {
		return
	}
	state.Inning = transition.InningNumber
	state.IsTop = transition.IsTop
	resetCount(state)
	clearBases(state)
	state.Outs = 0
}

func applySubstitution(state *dugoutv1.GameState, sub *dugoutv1.SubstitutionPayload) {
	// Substitutions keep IDs stable across bases and active batter/pitcher slots.
	if sub == nil {
		return
	}

	// Replace player ID on bases if matching
	if state.RunnerOnFirst && state.RunnerOnFirstPlayerId == sub.PlayerOutId {
		state.RunnerOnFirstPlayerId = sub.PlayerInId
	}
	if state.RunnerOnSecond && state.RunnerOnSecondPlayerId == sub.PlayerOutId {
		state.RunnerOnSecondPlayerId = sub.PlayerInId
	}
	if state.RunnerOnThird && state.RunnerOnThirdPlayerId == sub.PlayerOutId {
		state.RunnerOnThirdPlayerId = sub.PlayerInId
	}

	// Replace active batter/pitcher
	if state.ActiveBatterId == sub.PlayerOutId {
		state.ActiveBatterId = sub.PlayerInId
	}
	if state.ActivePitcherId == sub.PlayerOutId {
		state.ActivePitcherId = sub.PlayerInId
	}
}

func applyClockControl(state *dugoutv1.GameState, clock *dugoutv1.ClockControlPayload) {
	// Clock controls are pass-through game-clock state, separate from baseball scoring.
	if clock == nil {
		return
	}
	switch clock.Action {
	case dugoutv1.ClockAction_CLOCK_ACTION_START:
		state.IsClockRunning = true
	case dugoutv1.ClockAction_CLOCK_ACTION_STOP:
		state.IsClockRunning = false
	case dugoutv1.ClockAction_CLOCK_ACTION_RESET:
		state.GameClockSeconds = clock.SetTimeSeconds
	}
}

func applyCorrection(state *dugoutv1.GameState, corr *dugoutv1.GameCorrectionPayload) {
	// Corrections are authoritative manual overrides from the referee app.
	if corr == nil {
		return
	}
	state.Balls = corr.Balls
	state.Strikes = corr.Strikes
	state.Outs = corr.Outs
	state.HomeScore = corr.HomeScore
	state.AwayScore = corr.AwayScore
}

// Helper functions

func resetCount(state *dugoutv1.GameState) {
	// Counts reset after walks, strikeouts, balls in play, and inning transitions.
	state.Balls = 0
	state.Strikes = 0
}

func clearBases(state *dugoutv1.GameState) {
	// Clearing both occupancy booleans and IDs prevents stale runner labels.
	state.RunnerOnFirst = false
	state.RunnerOnFirstPlayerId = ""
	state.RunnerOnSecond = false
	state.RunnerOnSecondPlayerId = ""
	state.RunnerOnThird = false
	state.RunnerOnThirdPlayerId = ""
}

func addRuns(state *dugoutv1.GameState, runs int32) {
	// Top half means the away team is batting; bottom half means home is batting.
	if state.IsTop {
		state.AwayScore += runs
	} else {
		state.HomeScore += runs
	}
}

func advanceRunnersOnWalk(state *dugoutv1.GameState, batterID string) {
	// Walks only force occupied bases ahead of the batter.
	if !state.RunnerOnFirst {
		state.RunnerOnFirst = true
		state.RunnerOnFirstPlayerId = batterID
		return
	}

	if !state.RunnerOnSecond {
		state.RunnerOnSecond = true
		state.RunnerOnSecondPlayerId = state.RunnerOnFirstPlayerId
		state.RunnerOnFirstPlayerId = batterID
		return
	}

	if !state.RunnerOnThird {
		state.RunnerOnThird = true
		state.RunnerOnThirdPlayerId = state.RunnerOnSecondPlayerId
		state.RunnerOnSecondPlayerId = state.RunnerOnFirstPlayerId
		state.RunnerOnFirstPlayerId = batterID
		return
	}

	// Bases loaded walk scores a run
	addRuns(state, 1)
	state.RunnerOnThirdPlayerId = state.RunnerOnSecondPlayerId
	state.RunnerOnSecondPlayerId = state.RunnerOnFirstPlayerId
	state.RunnerOnFirstPlayerId = batterID
}

func advanceBattingIndex(state *dugoutv1.GameState) {
	// Batting order is modeled as a 1-based nine-player cycle.
	if state.IsTop {
		// Away team is batting
		state.BattingIndexAway = (state.BattingIndexAway % 9) + 1
	} else {
		// Home team is batting
		state.BattingIndexHome = (state.BattingIndexHome % 9) + 1
	}
}

func checkHalfInningEnd(state *dugoutv1.GameState) {
	// Three outs end the half inning and clear count/base state.
	if state.Outs >= 3 {
		resetCount(state)
		clearBases(state)
		transitionHalfInning(state)
	}
}

func transitionHalfInning(state *dugoutv1.GameState) {
	// Moving from bottom to top advances the inning number.
	state.Outs = 0
	if state.IsTop {
		state.IsTop = false
	} else {
		state.IsTop = true
		state.Inning++
	}
}

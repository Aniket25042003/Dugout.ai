// File: services/event-gateway/internal/reducer/reducer_test.go
// Layer: Tests — Baseball Game State Reducer
// Purpose: Verifies pitch, play, correction, substitution, and inning-transition
// reducer behavior for replayed event streams.
// Dependencies: Go testing package and generated Dugout contracts.
package reducer

import (
	"testing"

	"github.com/Aniket25042003/Dugout/packages/contracts/go/dugout/v1"
)

// Verifies that four balls reset the count, place the batter on first, and advance order.
func TestReduce_PitchBall(t *testing.T) {
	initialState := &dugoutv1.GameState{
		GameId:           "game_1",
		Balls:            0,
		Strikes:          0,
		Outs:             0,
		ActiveBatterId:   "batter_1",
		ActivePitcherId:  "pitcher_1",
		BattingIndexAway: 1,
		IsTop:            true,
		Inning:           1,
	}

	event := &dugoutv1.GameEvent{
		EventId: "evt_1",
		GameId:  "game_1",
		Payload: &dugoutv1.GameEvent_PitchResult{
			PitchResult: &dugoutv1.PitchResultPayload{
				Result:    dugoutv1.PitchResultType_PITCH_RESULT_TYPE_BALL,
				BatterId:  "batter_1",
				PitcherId: "pitcher_1",
			},
		},
	}

	// 1. One ball
	state := Reduce(initialState, event)
	if state.Balls != 1 {
		t.Errorf("Expected 1 ball, got %d", state.Balls)
	}

	// 2. Three more balls -> Walk
	state = Reduce(state, event)
	state = Reduce(state, event)
	state = Reduce(state, event)

	if state.Balls != 0 {
		t.Errorf("Expected count to reset, got %d balls", state.Balls)
	}
	if !state.RunnerOnFirst {
		t.Error("Expected runner on first after walk")
	}
	if state.RunnerOnFirstPlayerId != "batter_1" {
		t.Errorf("Expected runner on first to be 'batter_1', got '%s'", state.RunnerOnFirstPlayerId)
	}
	if state.BattingIndexAway != 2 {
		t.Errorf("Expected batting index to advance to 2, got %d", state.BattingIndexAway)
	}
}

// Verifies that three strikes reset the count, record an out, and advance order.
func TestReduce_PitchStrikeout(t *testing.T) {
	initialState := &dugoutv1.GameState{
		GameId:           "game_1",
		Balls:            0,
		Strikes:          0,
		Outs:             0,
		ActiveBatterId:   "batter_1",
		ActivePitcherId:  "pitcher_1",
		BattingIndexAway: 1,
		IsTop:            true,
		Inning:           1,
	}

	event := &dugoutv1.GameEvent{
		EventId: "evt_1",
		GameId:  "game_1",
		Payload: &dugoutv1.GameEvent_PitchResult{
			PitchResult: &dugoutv1.PitchResultPayload{
				Result:    dugoutv1.PitchResultType_PITCH_RESULT_TYPE_STRIKE_LOOKING,
				BatterId:  "batter_1",
				PitcherId: "pitcher_1",
			},
		},
	}

	state := Reduce(initialState, event)
	state = Reduce(state, event)
	state = Reduce(state, event) // 3rd strike -> out

	if state.Strikes != 0 {
		t.Errorf("Expected strikes to reset, got %d", state.Strikes)
	}
	if state.Outs != 1 {
		t.Errorf("Expected 1 out, got %d", state.Outs)
	}
	if state.BattingIndexAway != 2 {
		t.Errorf("Expected batting index to advance, got %d", state.BattingIndexAway)
	}
}

// Verifies base advancement and scoring for doubles followed by home runs.
func TestReduce_PlayOutcome_Hits(t *testing.T) {
	// Start with base runner on 1st
	initialState := &dugoutv1.GameState{
		GameId:                "game_1",
		ActiveBatterId:        "batter_2",
		RunnerOnFirst:         true,
		RunnerOnFirstPlayerId: "batter_1",
		IsTop:                 true,
		Inning:                1,
		BattingIndexAway:      2,
		AwayScore:             0,
	}

	// Batter 2 hits a double
	doubleEvent := &dugoutv1.GameEvent{
		EventId: "evt_double",
		GameId:  "game_1",
		Payload: &dugoutv1.GameEvent_PlayOutcome{
			PlayOutcome: &dugoutv1.PlayOutcomePayload{
				Type:     dugoutv1.PlayOutcomeType_PLAY_OUTCOME_TYPE_DOUBLE,
				BatterId: "batter_2",
			},
		},
	}

	state := Reduce(initialState, doubleEvent)

	// Runner on 1st goes to 3rd
	if !state.RunnerOnThird {
		t.Error("Expected runner on third after double with runner on 1st")
	}
	if state.RunnerOnThirdPlayerId != "batter_1" {
		t.Errorf("Expected runner on third to be 'batter_1', got '%s'", state.RunnerOnThirdPlayerId)
	}

	// Batter is on 2nd
	if !state.RunnerOnSecond {
		t.Error("Expected batter on second")
	}
	if state.RunnerOnSecondPlayerId != "batter_2" {
		t.Errorf("Expected runner on second to be 'batter_2', got '%s'", state.RunnerOnSecondPlayerId)
	}

	// 1st base is clear
	if state.RunnerOnFirst {
		t.Error("Expected first base to be empty")
	}

	// Away team scores should still be 0
	if state.AwayScore != 0 {
		t.Errorf("Expected score to be 0, got %d", state.AwayScore)
	}

	// Batter 3 hits a home run
	hrEvent := &dugoutv1.GameEvent{
		EventId: "evt_hr",
		GameId:  "game_1",
		Payload: &dugoutv1.GameEvent_PlayOutcome{
			PlayOutcome: &dugoutv1.PlayOutcomePayload{
				Type:     dugoutv1.PlayOutcomeType_PLAY_OUTCOME_TYPE_HOME_RUN,
				BatterId: "batter_3",
			},
		},
	}

	state = Reduce(state, hrEvent)

	// Home run scores everyone (batter_1, batter_2, batter_3 = 3 runs)
	if state.AwayScore != 3 {
		t.Errorf("Expected 3 runs, got %d", state.AwayScore)
	}

	// Bases should be empty
	if state.RunnerOnFirst || state.RunnerOnSecond || state.RunnerOnThird {
		t.Error("Expected bases to be cleared after home run")
	}
}

// Verifies that manual corrections overwrite count, outs, and score.
func TestReduce_Correction(t *testing.T) {
	initialState := &dugoutv1.GameState{
		GameId:    "game_1",
		Balls:     1,
		Strikes:   1,
		Outs:      1,
		HomeScore: 2,
		AwayScore: 1,
	}

	correctionEvent := &dugoutv1.GameEvent{
		EventId: "evt_correction",
		GameId:  "game_1",
		Payload: &dugoutv1.GameEvent_Correction{
			Correction: &dugoutv1.GameCorrectionPayload{
				Balls:     0,
				Strikes:   0,
				Outs:      2,
				HomeScore: 3,
				AwayScore: 1,
				Reason:    "Scorekeeper corrected home score and outs",
			},
		},
	}

	state := Reduce(initialState, correctionEvent)

	if state.Balls != 0 || state.Strikes != 0 || state.Outs != 2 || state.HomeScore != 3 || state.AwayScore != 1 {
		t.Errorf("Correction not applied correctly: %+v", state)
	}
}

// Verifies that substitutions update runner and active batter IDs.
func TestReduce_Substitution(t *testing.T) {
	initialState := &dugoutv1.GameState{
		GameId:                "game_1",
		ActiveBatterId:        "player_old_batter",
		ActivePitcherId:       "player_pitcher",
		RunnerOnFirst:         true,
		RunnerOnFirstPlayerId: "player_old_batter",
	}

	subEvent := &dugoutv1.GameEvent{
		EventId: "evt_sub",
		GameId:  "game_1",
		Payload: &dugoutv1.GameEvent_Substitution{
			Substitution: &dugoutv1.SubstitutionPayload{
				TeamId:      "team_home",
				PlayerInId:  "player_new_pinch_runner",
				PlayerOutId: "player_old_batter",
				Position:    "pinch_runner",
			},
		},
	}

	state := Reduce(initialState, subEvent)

	if state.RunnerOnFirstPlayerId != "player_new_pinch_runner" {
		t.Errorf("Expected runner on first to be substituted, got '%s'", state.RunnerOnFirstPlayerId)
	}
	if state.ActiveBatterId != "player_new_pinch_runner" {
		t.Errorf("Expected active batter to be substituted, got '%s'", state.ActiveBatterId)
	}
}

// Verifies that the third out transitions from top to bottom of the inning.
func TestReduce_ThreeOutsTransition(t *testing.T) {
	initialState := &dugoutv1.GameState{
		GameId:           "game_1",
		Outs:             2,
		IsTop:            true,
		Inning:           1,
		BattingIndexAway: 3,
	}

	event := &dugoutv1.GameEvent{
		EventId: "evt_strikeout",
		GameId:  "game_1",
		Payload: &dugoutv1.GameEvent_PitchResult{
			PitchResult: &dugoutv1.PitchResultPayload{
				Result: dugoutv1.PitchResultType_PITCH_RESULT_TYPE_STRIKE_LOOKING,
			},
		},
	}

	// 2 strikes
	state := Reduce(initialState, event)
	state = Reduce(state, event)
	// 3rd strike -> 3rd out -> Inning transition
	state = Reduce(state, event)

	if state.Outs != 0 {
		t.Errorf("Expected outs to reset, got %d", state.Outs)
	}
	if state.IsTop {
		t.Error("Expected inning to transition from Top to Bottom")
	}
	if state.Inning != 1 {
		t.Errorf("Expected Inning 1 Bottom, got Inning %d", state.Inning)
	}
}

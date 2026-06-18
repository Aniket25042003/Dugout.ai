/**
 * @file apps/referee-mobile/App.tsx
 * @layer Mobile — Referee Scoring Interface
 * @description Provides the referee's touch interface for official pitch, play,
 *              inning, and correction events sent to the event gateway.
 * @dependencies React Native UI primitives, Expo StatusBar, event API client, offline queue
 */

import React, { useState, useCallback } from "react";
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ScrollView,
  Alert,
  SafeAreaView,
  TextInput,
  Modal,
} from "react-native";
import { StatusBar } from "expo-status-bar";
import {
  sendEvent,
  generateEventId,
  nextSequence,
  GameEventPayload,
  getGatewayUrl,
  setGatewayUrl,
} from "./src/api/client";
import { enqueueEvent, flushQueue, getQueueLength } from "./src/api/eventQueue";

const GAME_ID = "game_2026_ashland_vs_opponent";
const SOURCE = "referee_app";
const DEVICE_ID = "ref_phone_1";

type GameState = {
  balls: number;
  strikes: number;
  outs: number;
  inning: number;
  isTop: boolean;
  homeScore: number;
  awayScore: number;
};

/** Local scoreboard/count state mirrored immediately after referee taps. */

/**
 * Renders the referee mobile scoring app.
 *
 * @returns React Native app for creating official game events
 */
export default function App() {
  const [gameState, setGameState] = useState<GameState>({
    balls: 0,
    strikes: 0,
    outs: 0,
    inning: 1,
    isTop: true,
    homeScore: 0,
    awayScore: 0,
  });

  const [showCorrection, setShowCorrection] = useState(false);
  const [correctionBalls, setCorrectionBalls] = useState("0");
  const [correctionStrikes, setCorrectionStrikes] = useState("0");
  const [correctionOuts, setCorrectionOuts] = useState("0");
  const [correctionHome, setCorrectionHome] = useState("0");
  const [correctionAway, setCorrectionAway] = useState("0");
  const [correctionReason, setCorrectionReason] = useState("");
  const [pendingCount, setPendingCount] = useState(0);
  const [lastAction, setLastAction] = useState("Ready");
  const [serverUrl, setServerUrlState] = useState(getGatewayUrl());

  const handleServerUrlChange = useCallback((url: string) => {
    /**
     * Updates the event gateway URL from the editable server field.
     *
     * @param url - New gateway base URL
     */
    setServerUrlState(url);
    setGatewayUrl(url);
  }, []);

  const submitEvent = useCallback(async (event: GameEventPayload) => {
    /**
     * Sends an event immediately or queues it for retry when offline.
     *
     * @param event - Official game event payload
     */
    const success = await sendEvent(event);
    if (!success) {
      enqueueEvent(event);
      setPendingCount(getQueueLength());
      setLastAction(`⚠ Queued offline (${getQueueLength()} pending)`);
    } else {
      setLastAction(`✓ Sent: ${event.pitchResult?.result || event.playOutcome?.type || event.inningTransition ? "inning" : "event"}`);
      // A successful send indicates connectivity, so retry older queued events.
      if (getQueueLength() > 0) {
        const flushed = await flushQueue();
        setPendingCount(getQueueLength());
        if (flushed > 0) {
          setLastAction(`✓ Sent + flushed ${flushed} queued`);
        }
      }
    }
  }, []);

  const handlePitch = useCallback(
    (result: string) => {
      /**
       * Creates a pitch result event and mirrors count changes locally.
       *
       * @param result - Contract enum string for the pitch result
       */
      const event: GameEventPayload = {
        eventId: generateEventId(),
        gameId: GAME_ID,
        source: SOURCE,
        sourceDeviceId: DEVICE_ID,
        occurredAt: new Date().toISOString(),
        sequence: nextSequence(),
        confidence: 1.0,
        authority: "official",
        pitchResult: {
          result,
          pitcherId: "pitcher_active",
          batterId: "batter_active",
        },
      };

      // Local display updates keep the referee UI responsive before gateway replay.
      setGameState((prev) => {
        const next = { ...prev };
        if (result === "PITCH_RESULT_TYPE_BALL") {
          next.balls++;
          if (next.balls >= 4) {
            next.balls = 0;
            next.strikes = 0;
          }
        } else if (
          result === "PITCH_RESULT_TYPE_STRIKE_LOOKING" ||
          result === "PITCH_RESULT_TYPE_STRIKE_SWINGING"
        ) {
          next.strikes++;
          if (next.strikes >= 3) {
            next.balls = 0;
            next.strikes = 0;
            next.outs++;
            if (next.outs >= 3) {
              next.outs = 0;
              if (next.isTop) {
                next.isTop = false;
              } else {
                next.isTop = true;
                next.inning++;
              }
            }
          }
        } else if (result === "PITCH_RESULT_TYPE_FOUL") {
          if (next.strikes < 2) next.strikes++;
        }
        return next;
      });

      submitEvent(event);
    },
    [submitEvent]
  );

  const handlePlayOutcome = useCallback(
    (type: string, runsScored: number = 0, outsRecorded: number = 0) => {
      /**
       * Creates a play outcome event and mirrors score/out changes locally.
       *
       * @param type - Contract enum string for the play outcome
       * @param runsScored - Runs scored on the play
       * @param outsRecorded - Outs recorded on the play
       */
      const event: GameEventPayload = {
        eventId: generateEventId(),
        gameId: GAME_ID,
        source: SOURCE,
        sourceDeviceId: DEVICE_ID,
        occurredAt: new Date().toISOString(),
        sequence: nextSequence(),
        confidence: 1.0,
        authority: "official",
        playOutcome: {
          type,
          runsScored,
          outsRecorded,
          batterId: "batter_active",
        },
      };

      setGameState((prev) => {
        const next = { ...prev };
        next.balls = 0;
        next.strikes = 0;
        next.outs += outsRecorded;

        if (type === "PLAY_OUTCOME_TYPE_HOME_RUN") {
          if (next.isTop) next.awayScore += runsScored;
          else next.homeScore += runsScored;
        } else if (runsScored > 0) {
          if (next.isTop) next.awayScore += runsScored;
          else next.homeScore += runsScored;
        }

        if (next.outs >= 3) {
          next.outs = 0;
          if (next.isTop) {
            next.isTop = false;
          } else {
            next.isTop = true;
            next.inning++;
          }
        }
        return next;
      });

      submitEvent(event);
    },
    [submitEvent]
  );

  const handleInningTransition = useCallback(() => {
    /**
     * Advances the local inning half and emits an inning transition event.
     */
    setGameState((prev) => {
      const next = { ...prev };
      next.balls = 0;
      next.strikes = 0;
      next.outs = 0;
      if (next.isTop) {
        next.isTop = false;
      } else {
        next.isTop = true;
        next.inning++;
      }

      const event: GameEventPayload = {
        eventId: generateEventId(),
        gameId: GAME_ID,
        source: SOURCE,
        sourceDeviceId: DEVICE_ID,
        occurredAt: new Date().toISOString(),
        sequence: nextSequence(),
        confidence: 1.0,
        authority: "official",
        inningTransition: {
          inningNumber: next.inning,
          isTop: next.isTop,
        },
      };
      submitEvent(event);

      return next;
    });
  }, [submitEvent]);

  const handleCorrection = useCallback(() => {
    /**
     * Emits a manual correction event from modal values and updates local display.
     */
    const event: GameEventPayload = {
      eventId: generateEventId(),
      gameId: GAME_ID,
      source: SOURCE,
      sourceDeviceId: DEVICE_ID,
      occurredAt: new Date().toISOString(),
      sequence: nextSequence(),
      confidence: 1.0,
      authority: "official",
      correction: {
        balls: parseInt(correctionBalls, 10) || 0,
        strikes: parseInt(correctionStrikes, 10) || 0,
        outs: parseInt(correctionOuts, 10) || 0,
        homeScore: parseInt(correctionHome, 10) || 0,
        awayScore: parseInt(correctionAway, 10) || 0,
        reason: correctionReason || "Manual correction by referee",
      },
    };

    setGameState({
      balls: parseInt(correctionBalls, 10) || 0,
      strikes: parseInt(correctionStrikes, 10) || 0,
      outs: parseInt(correctionOuts, 10) || 0,
      homeScore: parseInt(correctionHome, 10) || 0,
      awayScore: parseInt(correctionAway, 10) || 0,
      inning: gameState.inning,
      isTop: gameState.isTop,
    });

    submitEvent(event);
    setShowCorrection(false);
    setLastAction("✓ Correction applied");
  }, [
    correctionBalls,
    correctionStrikes,
    correctionOuts,
    correctionHome,
    correctionAway,
    correctionReason,
    gameState.inning,
    gameState.isTop,
    submitEvent,
  ]);

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />

      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>⚾ DUGOUT REFEREE</Text>
        <Text style={styles.headerStatus}>{lastAction}</Text>
        {pendingCount > 0 && (
          <Text style={styles.pendingBadge}>
            {pendingCount} queued
          </Text>
        )}
      </View>

      {/* Server Config Row */}
      <View style={styles.configRow}>
        <Text style={styles.configLabel}>Server:</Text>
        <TextInput
          style={styles.configInput}
          value={serverUrl}
          onChangeText={handleServerUrlChange}
          placeholder="http://192.168.1.34:8080"
          placeholderTextColor="#6b7280"
          autoCapitalize="none"
          autoCorrect={false}
        />
      </View>

      {/* Scoreboard */}
      <View style={styles.scoreboard}>
        <View style={styles.scoreRow}>
          <Text style={styles.teamLabel}>
            {gameState.isTop ? "▶ AWAY" : "  AWAY"}
          </Text>
          <Text style={styles.scoreValue}>{gameState.awayScore}</Text>
        </View>
        <View style={styles.scoreRow}>
          <Text style={styles.teamLabel}>
            {!gameState.isTop ? "▶ HOME" : "  HOME"}
          </Text>
          <Text style={styles.scoreValue}>{gameState.homeScore}</Text>
        </View>
        <View style={styles.inningRow}>
          <Text style={styles.inningText}>
            {gameState.isTop ? "▲" : "▼"} {gameState.inning}
          </Text>
          <Text style={styles.countText}>
            {gameState.balls}-{gameState.strikes} | {gameState.outs} Out
          </Text>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.buttonsContainer}>
        {/* Pitch Result Buttons */}
        <Text style={styles.sectionLabel}>PITCH RESULT</Text>
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.btn, styles.btnBall]}
            onPress={() => handlePitch("PITCH_RESULT_TYPE_BALL")}
          >
            <Text style={styles.btnText}>BALL</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.btn, styles.btnStrike]}
            onPress={() => handlePitch("PITCH_RESULT_TYPE_STRIKE_LOOKING")}
          >
            <Text style={styles.btnText}>STRIKE{"\n"}(LOOKING)</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.btn, styles.btnStrike]}
            onPress={() => handlePitch("PITCH_RESULT_TYPE_STRIKE_SWINGING")}
          >
            <Text style={styles.btnText}>STRIKE{"\n"}(SWINGING)</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.btn, styles.btnFoul]}
            onPress={() => handlePitch("PITCH_RESULT_TYPE_FOUL")}
          >
            <Text style={styles.btnText}>FOUL</Text>
          </TouchableOpacity>
        </View>

        {/* Play Outcome Buttons */}
        <Text style={styles.sectionLabel}>PLAY OUTCOME</Text>
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.btn, styles.btnOut]}
            onPress={() =>
              handlePlayOutcome("PLAY_OUTCOME_TYPE_OUT", 0, 1)
            }
          >
            <Text style={styles.btnText}>OUT</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.btn, styles.btnHit]}
            onPress={() => handlePlayOutcome("PLAY_OUTCOME_TYPE_SINGLE")}
          >
            <Text style={styles.btnText}>SINGLE</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.btn, styles.btnHit]}
            onPress={() => handlePlayOutcome("PLAY_OUTCOME_TYPE_DOUBLE")}
          >
            <Text style={styles.btnText}>DOUBLE</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.btn, styles.btnHit]}
            onPress={() => handlePlayOutcome("PLAY_OUTCOME_TYPE_TRIPLE")}
          >
            <Text style={styles.btnText}>TRIPLE</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.btn, styles.btnHR]}
            onPress={() =>
              handlePlayOutcome("PLAY_OUTCOME_TYPE_HOME_RUN", 1, 0)
            }
          >
            <Text style={styles.btnText}>HOME RUN</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.btn, styles.btnWalk]}
            onPress={() => handlePlayOutcome("PLAY_OUTCOME_TYPE_WALK")}
          >
            <Text style={styles.btnText}>WALK</Text>
          </TouchableOpacity>
        </View>

        {/* Game Control Buttons */}
        <Text style={styles.sectionLabel}>GAME CONTROLS</Text>
        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[styles.btn, styles.btnInning]}
            onPress={handleInningTransition}
          >
            <Text style={styles.btnText}>NEXT{"\n"}HALF INNING</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.btn, styles.btnCorrection]}
            onPress={() => {
              setCorrectionBalls(String(gameState.balls));
              setCorrectionStrikes(String(gameState.strikes));
              setCorrectionOuts(String(gameState.outs));
              setCorrectionHome(String(gameState.homeScore));
              setCorrectionAway(String(gameState.awayScore));
              setCorrectionReason("");
              setShowCorrection(true);
            }}
          >
            <Text style={styles.btnText}>CORRECTION</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>

      {/* Correction Modal */}
      <Modal visible={showCorrection} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Manual Correction</Text>

            <View style={styles.corrRow}>
              <Text style={styles.corrLabel}>Balls:</Text>
              <TextInput style={styles.corrInput} value={correctionBalls} onChangeText={setCorrectionBalls} keyboardType="number-pad" />
              <Text style={styles.corrLabel}>Strikes:</Text>
              <TextInput style={styles.corrInput} value={correctionStrikes} onChangeText={setCorrectionStrikes} keyboardType="number-pad" />
            </View>
            <View style={styles.corrRow}>
              <Text style={styles.corrLabel}>Outs:</Text>
              <TextInput style={styles.corrInput} value={correctionOuts} onChangeText={setCorrectionOuts} keyboardType="number-pad" />
            </View>
            <View style={styles.corrRow}>
              <Text style={styles.corrLabel}>Home:</Text>
              <TextInput style={styles.corrInput} value={correctionHome} onChangeText={setCorrectionHome} keyboardType="number-pad" />
              <Text style={styles.corrLabel}>Away:</Text>
              <TextInput style={styles.corrInput} value={correctionAway} onChangeText={setCorrectionAway} keyboardType="number-pad" />
            </View>
            <View style={styles.corrRow}>
              <Text style={styles.corrLabel}>Reason:</Text>
              <TextInput style={[styles.corrInput, { flex: 3 }]} value={correctionReason} onChangeText={setCorrectionReason} placeholder="e.g. wrong count" placeholderTextColor="#888" />
            </View>

            <View style={styles.buttonRow}>
              <TouchableOpacity style={[styles.btn, styles.btnHit]} onPress={handleCorrection}>
                <Text style={styles.btnText}>APPLY</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.btn, styles.btnOut]} onPress={() => setShowCorrection(false)}>
                <Text style={styles.btnText}>CANCEL</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0a0e1a",
  },
  header: {
    paddingTop: 8,
    paddingHorizontal: 16,
    paddingBottom: 8,
    backgroundColor: "#111827",
    borderBottomWidth: 1,
    borderBottomColor: "#1f2937",
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  headerTitle: {
    color: "#f59e0b",
    fontSize: 18,
    fontWeight: "800",
  },
  headerStatus: {
    color: "#9ca3af",
    fontSize: 12,
    flex: 1,
  },
  configRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#1f2937",
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#374151",
    gap: 8,
  },
  configLabel: {
    color: "#9ca3af",
    fontSize: 12,
    fontWeight: "600",
  },
  configInput: {
    flex: 1,
    backgroundColor: "#111827",
    color: "#fff",
    fontSize: 12,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: "#374151",
    fontFamily: "monospace",
  },
  pendingBadge: {
    color: "#fbbf24",
    backgroundColor: "#78350f",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
    fontSize: 11,
    fontWeight: "700",
    overflow: "hidden",
  },
  scoreboard: {
    backgroundColor: "#1e1e2e",
    marginHorizontal: 12,
    marginTop: 10,
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: "#2d2d44",
  },
  scoreRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 4,
  },
  teamLabel: {
    color: "#d1d5db",
    fontSize: 16,
    fontWeight: "700",
    fontFamily: "monospace",
  },
  scoreValue: {
    color: "#fbbf24",
    fontSize: 28,
    fontWeight: "900",
    fontFamily: "monospace",
  },
  inningRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 8,
    borderTopWidth: 1,
    borderTopColor: "#374151",
    paddingTop: 8,
  },
  inningText: {
    color: "#818cf8",
    fontSize: 18,
    fontWeight: "800",
  },
  countText: {
    color: "#9ca3af",
    fontSize: 16,
    fontWeight: "600",
    fontFamily: "monospace",
  },
  buttonsContainer: {
    paddingHorizontal: 12,
    paddingBottom: 24,
  },
  sectionLabel: {
    color: "#6b7280",
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.5,
    marginTop: 16,
    marginBottom: 6,
    marginLeft: 4,
  },
  buttonRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: 8,
  },
  btn: {
    flex: 1,
    paddingVertical: 22,
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 70,
  },
  btnText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "800",
    textAlign: "center",
    lineHeight: 20,
  },
  btnBall: { backgroundColor: "#1d4ed8" },
  btnStrike: { backgroundColor: "#dc2626" },
  btnFoul: { backgroundColor: "#7c3aed" },
  btnOut: { backgroundColor: "#b91c1c" },
  btnHit: { backgroundColor: "#059669" },
  btnHR: { backgroundColor: "#d97706" },
  btnWalk: { backgroundColor: "#0284c7" },
  btnInning: { backgroundColor: "#4338ca" },
  btnCorrection: { backgroundColor: "#6b21a8" },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.8)",
    justifyContent: "center",
    padding: 20,
  },
  modalContent: {
    backgroundColor: "#1e1e2e",
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: "#374151",
  },
  modalTitle: {
    color: "#f59e0b",
    fontSize: 20,
    fontWeight: "800",
    marginBottom: 16,
    textAlign: "center",
  },
  corrRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 10,
    gap: 8,
  },
  corrLabel: {
    color: "#d1d5db",
    fontSize: 14,
    fontWeight: "600",
    width: 60,
  },
  corrInput: {
    flex: 1,
    backgroundColor: "#111827",
    color: "#fff",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 16,
    borderWidth: 1,
    borderColor: "#374151",
  },
});

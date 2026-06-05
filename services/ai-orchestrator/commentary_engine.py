"""
Commentary Engine for Dugout.ai.
Generates play-by-play baseball commentary using a local LLM (Ollama)
and synthesizes it to speech using Piper TTS.
"""

import asyncio
import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger("ai-orchestrator-commentary")

SYSTEM_PROMPT = """
You are a professional, formal baseball radio broadcast announcer.
Your commentary should be play-by-play, describing the event that just occurred, using the active player names, stats, and the current game situation.
Keep your commentary concise (1 to 2 sentences max) and highly realistic. Do not invent any facts or players not mentioned in the context.
If no player name is available, refer to them by their position or jersey number.
"""

class CommentaryEngine:
    """
    Commentary Engine that orchestrates LLM generation, TTS synthesis, NATS publishing,
    and commentary audit logs.
    """

    def __init__(self, db_client, llm_client, tts_client, media_manager, nats_conn=None):
        self.db = db_client
        self.llm = llm_client
        self.tts = tts_client
        self.media = media_manager
        self.nc = nats_conn
        self.muted = False
        self.manual_mode = False
        self._game_states = {}  # game_id -> GameState dict

    def set_muted(self, muted: bool):
        self.muted = muted
        logger.info("Commentary engine muted: %s", muted)

    def set_manual_mode(self, manual: bool):
        self.manual_mode = manual
        logger.info("Commentary engine manual mode: %s", manual)

    async def get_or_create_game_state(self, game_id: str) -> dict:
        """Get or initialize the reduced game state for a game."""
        if game_id not in self._game_states:
            # Initialize with default v1 GameState fields
            self._game_states[game_id] = {
                "balls": 0,
                "strikes": 0,
                "outs": 0,
                "homeScore": 0,
                "awayScore": 0,
                "inning": 1,
                "isTop": True,
                "runnerOnFirst": False,
                "runnerOnFirstPlayerId": "",
                "runnerOnSecond": False,
                "runnerOnSecondPlayerId": "",
                "runnerOnThird": False,
                "runnerOnThirdPlayerId": "",
                "activeBatterId": "",
                "activePitcherId": "",
            }
        return self._game_states[game_id]

    def update_game_state_from_event(self, state: dict, event: dict):
        """Locally reduce/apply the event to our game state model."""
        pitch = event.get("pitchResult")
        play = event.get("playOutcome")
        transition = event.get("inningTransition")
        sub = event.get("substitution")
        corr = event.get("correction")

        if pitch:
            if pitch.get("pitcherId"):
                state["activePitcherId"] = pitch["pitcherId"]
            if pitch.get("batterId"):
                state["activeBatterId"] = pitch["batterId"]

            result = pitch.get("result", "")
            if "BALL" in result:
                state["balls"] += 1
                if state["balls"] >= 4:
                    self._advance_runners_on_walk(state, state["activeBatterId"])
                    state["balls"] = 0
                    state["strikes"] = 0
            elif "STRIKE_LOOKING" in result or "STRIKE_SWINGING" in result:
                state["strikes"] += 1
                if state["strikes"] >= 3:
                    state["outs"] += 1
                    state["balls"] = 0
                    state["strikes"] = 0
                    self._check_inning_end(state)
            elif "FOUL" in result:
                if state["strikes"] < 2:
                    state["strikes"] += 1
            elif "HIT_BY_PITCH" in result:
                self._advance_runners_on_walk(state, state["activeBatterId"])
                state["balls"] = 0
                state["strikes"] = 0
            elif "PUT_IN_PLAY" in result:
                state["balls"] = 0
                state["strikes"] = 0

        elif play:
            state["balls"] = 0
            state["strikes"] = 0
            state["outs"] += play.get("outsRecorded", 0)
            
            runs = play.get("runsScored", 0)
            if runs > 0:
                self._add_runs(state, runs)

            if state["outs"] >= 3:
                state["balls"] = 0
                state["strikes"] = 0
                self._clear_bases(state)
                self._transition_half_inning(state)
                return

            play_type = play.get("type", "")
            batter_id = play.get("batterId", state["activeBatterId"])

            if "SINGLE" in play_type:
                if state["runnerOnThird"]:
                    self._add_runs(state, 1)
                state["runnerOnThird"] = state["runnerOnSecond"]
                state["runnerOnThirdPlayerId"] = state["runnerOnSecondPlayerId"]
                state["runnerOnSecond"] = state["runnerOnFirst"]
                state["runnerOnSecondPlayerId"] = state["runnerOnFirstPlayerId"]
                state["runnerOnFirst"] = True
                state["runnerOnFirstPlayerId"] = batter_id

            elif "DOUBLE" in play_type:
                if state["runnerOnThird"]:
                    self._add_runs(state, 1)
                if state["runnerOnSecond"]:
                    self._add_runs(state, 1)
                state["runnerOnThird"] = state["runnerOnFirst"]
                state["runnerOnThirdPlayerId"] = state["runnerOnFirstPlayerId"]
                state["runnerOnSecond"] = True
                state["runnerOnSecondPlayerId"] = batter_id
                state["runnerOnFirst"] = False
                state["runnerOnFirstPlayerId"] = ""

            elif "TRIPLE" in play_type:
                if state["runnerOnThird"]:
                    self._add_runs(state, 1)
                if state["runnerOnSecond"]:
                    self._add_runs(state, 1)
                if state["runnerOnFirst"]:
                    self._add_runs(state, 1)
                state["runnerOnFirst"] = False
                state["runnerOnFirstPlayerId"] = ""
                state["runnerOnSecond"] = False
                state["runnerOnSecondPlayerId"] = ""
                state["runnerOnThird"] = True
                state["runnerOnThirdPlayerId"] = batter_id

            elif "HOME_RUN" in play_type:
                scored = 1
                if state["runnerOnThird"]:
                    scored += 1
                if state["runnerOnSecond"]:
                    scored += 1
                if state["runnerOnFirst"]:
                    scored += 1
                self._add_runs(state, scored)
                self._clear_bases(state)

            elif "WALK" in play_type:
                self._advance_runners_on_walk(state, batter_id)

        elif transition:
            state["inning"] = transition.get("inningNumber", 1)
            state["isTop"] = transition.get("isTop", True)
            state["balls"] = 0
            state["strikes"] = 0
            state["outs"] = 0
            self._clear_bases(state)

        elif sub:
            if state["runnerOnFirst"] and state["runnerOnFirstPlayerId"] == sub.get("playerOutId"):
                state["runnerOnFirstPlayerId"] = sub.get("playerInId")
            if state["runnerOnSecond"] and state["runnerOnSecondPlayerId"] == sub.get("playerOutId"):
                state["runnerOnSecondPlayerId"] = sub.get("playerInId")
            if state["runnerOnThird"] and state["runnerOnThirdPlayerId"] == sub.get("playerOutId"):
                state["runnerOnThirdPlayerId"] = sub.get("playerInId")

            if state["activeBatterId"] == sub.get("playerOutId"):
                state["activeBatterId"] = sub.get("playerInId")
            if state["activePitcherId"] == sub.get("playerOutId"):
                state["activePitcherId"] = sub.get("playerInId")

        elif corr:
            state["balls"] = corr.get("balls", 0)
            state["strikes"] = corr.get("strikes", 0)
            state["outs"] = corr.get("outs", 0)
            state["homeScore"] = corr.get("homeScore", 0)
            state["awayScore"] = corr.get("awayScore", 0)

    def _add_runs(self, state: dict, runs: int):
        if state["isTop"]:
            state["awayScore"] += runs
        else:
            state["homeScore"] += runs

    def _clear_bases(self, state: dict):
        state["runnerOnFirst"] = False
        state["runnerOnFirstPlayerId"] = ""
        state["runnerOnSecond"] = False
        state["runnerOnSecondPlayerId"] = ""
        state["runnerOnThird"] = False
        state["runnerOnThirdPlayerId"] = ""

    def _transition_half_inning(self, state: dict):
        state["outs"] = 0
        if state["isTop"]:
            state["isTop"] = False
        else:
            state["isTop"] = True
            state["inning"] += 1

    def _check_inning_end(self, state: dict):
        if state["outs"] >= 3:
            state["balls"] = 0
            state["strikes"] = 0
            self._clear_bases(state)
            self._transition_half_inning(state)

    def _advance_runners_on_walk(self, state: dict, batter_id: str):
        if not state["runnerOnFirst"]:
            state["runnerOnFirst"] = True
            state["runnerOnFirstPlayerId"] = batter_id
            return
        if not state["runnerOnSecond"]:
            state["runnerOnSecond"] = True
            state["runnerOnSecondPlayerId"] = state["runnerOnFirstPlayerId"]
            state["runnerOnFirstPlayerId"] = batter_id
            return
        if not state["runnerOnThird"]:
            state["runnerOnThird"] = True
            state["runnerOnThirdPlayerId"] = state["runnerOnSecondPlayerId"]
            state["runnerOnSecondPlayerId"] = state["runnerOnFirstPlayerId"]
            state["runnerOnFirstPlayerId"] = batter_id
            return
        self._add_runs(state, 1)
        state["runnerOnThirdPlayerId"] = state["runnerOnSecondPlayerId"]
        state["runnerOnSecondPlayerId"] = state["runnerOnFirstPlayerId"]
        state["runnerOnFirstPlayerId"] = batter_id

    async def generate_commentary(self, game_id: str, event_data: dict) -> Optional[dict]:
        """
        Generate play-by-play commentary text using Ollama (Llama 3.2 1b)
        and synthesize to speech with Piper.
        """
        event_id = event_data.get("eventId", f"evt_{uuid_short()}")
        
        # 1. Update/get Game State
        state = await self.get_or_create_game_state(game_id)
        self.update_game_state_from_event(state, event_data)

        if self.manual_mode:
            logger.info("Commentary is in MANUAL mode, skipping auto generation.")
            return None

        # Publish generating status
        await self._publish_status("generating", "", state)

        # 2. Build Context Snapshot
        context_snapshot = {
            "scoreboard": state.copy(),
            "event": event_data,
        }

        # Resolve player names and stats
        batter_name = "Unknown Batter"
        batter_stats = ""
        pitcher_name = "Unknown Pitcher"
        pitcher_stats = ""

        if state["activeBatterId"]:
            batter = await self.db.get_player_by_id(state["activeBatterId"])
            if batter:
                batter_name = batter["name"]
                stats = await self.db.get_player_stats(batter["id"])
                if stats:
                    batter_stats = f"Avg: {stats.get('batting_avg')}, HR: {stats.get('home_runs')}, RBI: {stats.get('rbis')}"

        if state["activePitcherId"]:
            pitcher = await self.db.get_player_by_id(state["activePitcherId"])
            if pitcher:
                pitcher_name = pitcher["name"]
                stats = await self.db.get_player_stats(pitcher["id"])
                if stats:
                    pitcher_stats = f"ERA: {stats.get('era')}, WHIP: {stats.get('whip')}, SO: {stats.get('pitch_strikeouts')}"

        context_snapshot["batter"] = {"name": batter_name, "stats": batter_stats}
        context_snapshot["pitcher"] = {"name": pitcher_name, "stats": pitcher_stats}

        # 3. Create Prompt
        prompt = self._build_prompt(state, event_data, batter_name, batter_stats, pitcher_name, pitcher_stats)

        # 4. Generate Commentary Text
        commentary_text = ""
        source = "llm"
        llm_info = {}

        # Check if Ollama is available
        llm_available = await self.llm.check_health()
        if llm_available:
            logger.info("Ollama is available. Generating commentary via LLM...")
            start_time = time.time()
            res = await self.llm.generate(prompt, SYSTEM_PROMPT)
            gen_time_ms = int((time.time() - start_time) * 1000)

            if res.get("text"):
                commentary_text = res["text"]
                llm_info = {
                    "model": "llama3.2:1b",
                    "prompt_tokens": res.get("prompt_tokens"),
                    "completion_tokens": res.get("completion_tokens"),
                    "generation_ms": gen_time_ms,
                }
            else:
                logger.warning("Ollama returned empty response, falling back to template")
                commentary_text = self._generate_fallback_template(event_data, batter_name, pitcher_name)
                source = "template"
        else:
            logger.warning("Ollama is offline. Falling back to template-based commentary.")
            commentary_text = self._generate_fallback_template(event_data, batter_name, pitcher_name)
            source = "template"

        logger.info("Generated Commentary: %s (Source: %s)", commentary_text, source)

        # 5. Synthesize TTS Audio
        audio_path_rel = ""
        audio_path_abs = ""
        tts_info = {}

        if commentary_text and not self.muted:
            audio_dir = os.path.join(self.media.resolve_path("media/audio/commentary"))
            os.makedirs(audio_dir, exist_ok=True)
            
            audio_filename = f"commentary_{event_id}.wav"
            audio_path_abs = os.path.join(audio_dir, audio_filename)
            audio_path_rel = f"media/audio/commentary/{audio_filename}"

            logger.info("Synthesizing TTS audio to %s...", audio_path_abs)
            start_time = time.time()
            tts_success = await self.tts.synthesize(commentary_text, audio_path_abs)
            tts_time_ms = int((time.time() - start_time) * 1000)

            if tts_success:
                tts_info = {
                    "model": "piper:en_US-lessac-medium",
                    "duration_ms": tts_time_ms,
                }
            else:
                logger.error("TTS synthesis failed.")
                audio_path_rel = ""

        # 6. Persist to Commentary History DB
        history_id = await self.db.save_commentary(
            game_id=game_id,
            text=commentary_text,
            source=source,
            source_event_ids=[event_id],
            audio_path=audio_path_rel or None,
            context_snapshot=context_snapshot,
            llm_model=llm_info.get("model"),
            generation_ms=llm_info.get("generation_ms"),
            tts_model=tts_info.get("model"),
            tts_duration_ms=tts_info.get("duration_ms"),
        )

        # 7. Publish Commentary State to NATS
        commentary_state = {
            "status": "speaking" if (audio_path_rel and not self.muted) else "idle",
            "currentText": commentary_text,
            "contextUsed": {
                "batterName": batter_name,
                "batterStats": batter_stats,
                "pitcherName": pitcher_name,
                "pitcherStats": pitcher_stats,
                "inning": state["inning"],
                "isTop": state["isTop"],
                "balls": state["balls"],
                "strikes": state["strikes"],
                "outs": state["outs"],
                "homeScore": state["homeScore"],
                "awayScore": state["awayScore"],
            },
            "audioPath": f"/media/audio/commentary/{audio_filename}" if audio_path_rel else "",
            "source": source,
            "historyId": history_id,
        }

        if self.nc:
            try:
                await self.nc.publish(
                    "dugout.production.commentary.state",
                    json.dumps(commentary_state).encode()
                )
                if audio_path_rel:
                    # Also publish audio path explicitly
                    await self.nc.publish(
                        "dugout.production.commentary.audio",
                        json.dumps({"audioPath": f"/media/audio/commentary/{audio_filename}"}).encode()
                    )
            except Exception as e:
                logger.error("Failed to publish commentary NATS states: %s", e)

        return commentary_state

    async def speak_manual(self, game_id: str, text: str) -> Optional[dict]:
        """Speak user-supplied manual commentary text."""
        logger.info("Speaking manual commentary: %s", text)
        state = await self.get_or_create_game_state(game_id)
        event_id = f"manual_{uuid_short()}"
        
        await self._publish_status("generating", text, state)

        audio_dir = os.path.join(self.media.resolve_path("media/audio/commentary"))
        os.makedirs(audio_dir, exist_ok=True)
        audio_filename = f"commentary_manual_{event_id}.wav"
        audio_path_abs = os.path.join(audio_dir, audio_filename)
        audio_path_rel = f"media/audio/commentary/{audio_filename}"

        start_time = time.time()
        tts_success = await self.tts.synthesize(text, audio_path_abs)
        tts_time_ms = int((time.time() - start_time) * 1000)

        # Save to DB
        history_id = await self.db.save_commentary(
            game_id=game_id,
            text=text,
            source="manual",
            source_event_ids=[],
            audio_path=audio_path_rel if tts_success else None,
            context_snapshot={"manual": True},
            tts_model="piper:en_US-lessac-medium" if tts_success else None,
            tts_duration_ms=tts_time_ms if tts_success else None,
        )

        commentary_state = {
            "status": "speaking" if tts_success else "idle",
            "currentText": text,
            "contextUsed": {"manual": True},
            "audioPath": f"/media/audio/commentary/{audio_filename}" if tts_success else "",
            "source": "manual",
            "historyId": history_id,
        }

        if self.nc:
            try:
                await self.nc.publish(
                    "dugout.production.commentary.state",
                    json.dumps(commentary_state).encode()
                )
                if tts_success:
                    await self.nc.publish(
                        "dugout.production.commentary.audio",
                        json.dumps({"audioPath": f"/media/audio/commentary/{audio_filename}"}).encode()
                    )
            except Exception as e:
                logger.error("Failed to publish manual commentary state: %s", e)

        return commentary_state

    def _build_prompt(self, state: dict, event: dict, batter: str, batter_stats: str, pitcher: str, pitcher_stats: str) -> str:
        half = "top" if state["isTop"] else "bottom"
        runners = []
        if state["runnerOnFirst"]:
            runners.append("runner on first")
        if state["runnerOnSecond"]:
            runners.append("runner on second")
        if state["runnerOnThird"]:
            runners.append("runner on third")
        
        runners_desc = ", ".join(runners) if runners else "bases empty"

        pitch_result = ""
        pitch = event.get("pitchResult")
        if pitch:
            pitch_result = f"Pitch result: {pitch.get('result')}"

        play_result = ""
        play = event.get("playOutcome")
        if play:
            play_result = f"Play outcome: {play.get('type')}, runs scored: {play.get('runsScored')}, outs recorded: {play.get('outsRecorded')}"

        inning_transition = ""
        transition = event.get("inningTransition")
        if transition:
            inning_transition = f"Inning transition: heading to the {half} of inning {transition.get('inningNumber')}"

        situation = f"""
Game Situation:
- Inning: {half} of inning {state['inning']}
- Score: Home {state['homeScore']} - Away {state['awayScore']}
- Outs: {state['outs']}
- Count: {state['balls']} balls, {state['strikes']} strikes
- Runners: {runners_desc}
- Current Batter: {batter} ({batter_stats})
- Current Pitcher: {pitcher} ({pitcher_stats})

Event description:
{pitch_result}
{play_result}
{inning_transition}
"""
        return situation

    def _generate_fallback_template(self, event_data: dict, batter: str, pitcher: str) -> str:
        """Simple template commentary fallback when LLM is slow/offline."""
        pitch = event_data.get("pitchResult")
        play = event_data.get("playOutcome")

        if pitch:
            result = pitch.get("result", "")
            if "BALL" in result:
                return f"Ball. Pitcher {pitcher} misses the zone."
            elif "STRIKE_LOOKING" in result:
                return f"Strike called, looking. A nice pitch from {pitcher}."
            elif "STRIKE_SWINGING" in result:
                return f"Swing and a miss! {pitcher} gets {batter} swinging."
            elif "FOUL" in result:
                return f"Fouled away. {batter} stays alive."
            elif "HIT_BY_PITCH" in result:
                return f"Ouch! {batter} is hit by pitch and takes first base."

        if play:
            outcome = play.get("type", "")
            if "SINGLE" in outcome:
                return f"Base hit! A single into the outfield by {batter}."
            elif "DOUBLE" in outcome:
                return f"A double! {batter} hits a line drive down the line."
            elif "TRIPLE" in outcome:
                return f"A triple! {batter} goes deep and slides into third."
            elif "HOME_RUN" in outcome:
                return f"It's outta here! Home run for {batter}!"
            elif "OUT" in outcome:
                return f"Out at first. Slick play by the defense."
            elif "WALK" in outcome:
                return f"Ball four. {batter} takes a walk."

        inning = event_data.get("inningTransition")
        if inning:
            num = inning.get("inningNumber", 1)
            top = inning.get("isTop", True)
            half = "top" if top else "bottom"
            return f"Moving to the {half} of the {num} Inning."

        return ""

    async def _publish_status(self, status: str, text: str, state: dict):
        if not self.nc:
            return
        try:
            await self.nc.publish(
                "dugout.production.commentary.state",
                json.dumps({
                    "status": status,
                    "currentText": text,
                    "contextUsed": {"inning": state["inning"], "isTop": state["isTop"]},
                    "audioPath": "",
                    "source": "manual" if text else "llm",
                }).encode()
            )
        except Exception as e:
            logger.error("Failed to publish commentary status: %s", e)

def uuid_short() -> str:
    import uuid
    return uuid.uuid4().hex[:12]

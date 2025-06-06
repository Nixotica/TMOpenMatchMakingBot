from datetime import datetime
import logging
import time
from typing import Dict, List, Optional
import discord
from discord.ext import commands, tasks

from aws.dynamodb import DynamoDbManager
from aws.s3 import S3ClientManager
from cogs import registry
from cogs.constants import (
    CHECK_ACTIVE_MATCHES_FINISHED_TASK_SEC,
    CHECK_KICK_QUEUED_PLAYERS_TASK_SEC,
    CHECK_QUEUES_TO_SPAWN_NEW_MATCH_TASK_SEC,
    COG_MATCHMAKING_MANAGER_V2,
    COLOR_EMBED,
    MAX_TIME_BEFORE_KICK_PLAYER_QUEUE_SEC,
)
from matchmaking.matches.event_creator import CreateMatchError
from matchmaking.mm_event_bus import MatchmakingManagerEventBus
from helpers import get_ping_channel
from matchmaking.match_queues.active_match_queue import ActiveMatchQueue
from matchmaking.match_queues.constants import (
    QUEUE_MANAGER_MIN_TIME_PING_FIRST_PLAYER_JOIN_QUEUE_SEC,
)
from matchmaking.match_queues.match_persistence import (
    get_persisted_matches,
    persist_match,
)
from matchmaking.matches.active_match import ActiveMatch
from matchmaking.matches.completed_match import CompletedMatch
from models.match_queue import MatchQueue
from models.player_profile import PlayerProfile


class MatchmakingManagerV2(commands.Cog):
    """
    The backbone of handling queueing, monitoring, and finishing matches.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.s3_manager = S3ClientManager()
        self.ddb_manager = DynamoDbManager()
        self.mm_event_bus = MatchmakingManagerEventBus()

        # Populate active queues to manage
        self.active_queues: List[ActiveMatchQueue] = []
        match_queues = self.ddb_manager.get_match_queues()
        logging.info(
            f"Instantiating matchmaking manager v2 with {len(match_queues)} active match queues."
        )
        for queue in match_queues:
            self.active_queues.append(ActiveMatchQueue(queue))

        # Retreive persisted matches from previous bot instance if exists
        persisted_matches = get_persisted_matches()
        logging.info(
            f"Instantiating matchmaking manager v2 with {len(persisted_matches)} persisted matches."
        )
        self.active_matches: List[ActiveMatch] = persisted_matches

        # Add the persisted matches as new active matches to be distributed to concerned parties
        for persisted_match in persisted_matches:
            # TODO - this is creating it before other cogs are registered, thus no subscribers pick it up.
            # Not urgent but it's worth addressing by doing this on some other oneshot task with delay
            self.mm_event_bus.add_new_active_match(persisted_match)

        # Map queue_id -> timestamp for detecting if should ping queue started
        self._last_queue_started_time: Dict[str, float] = {}

        registry.register_cog(COG_MATCHMAKING_MANAGER_V2, self)

    def cog_load(self):
        logging.info("Matchmaking Manager V2 loading...")

        self.check_queues_to_spawn_new_match.start()
        self.check_active_matches_to_complete.start()
        self.check_kick_queued_players.start()

    def cog_unload(self):
        logging.info("Matchmaking Manager V2 unloading...")

        self.check_queues_to_spawn_new_match.cancel()
        self.check_active_matches_to_complete.cancel()
        self.check_kick_queued_players.cancel()

    def add_queue(self, queue: MatchQueue) -> ActiveMatchQueue:
        """Adds a new active queue to the Matchmaking manager.

        Args:
            queue (MatchQueue): The queue to add and activate.

        Returns:
            ActiveMatchQueue: ActiveMatchQueue generated from this call.
        """
        active_queue = ActiveMatchQueue(queue)
        self.active_queues.append(active_queue)
        return active_queue

    def remove_queue(self, queue_id: str) -> bool:
        """Removes an active queue from the Matchmaking manager.
        If the bot reloads and the queue is "active" in DDB, it will re-activate.

        Args:
            queue_id (str): The queue to remove and deactivate.

        Returns:
            bool: True if the queue was found and removed, False if not found.
        """
        for queue in self.active_queues:
            if queue.queue.queue_id == queue_id:
                self.active_queues.remove(queue)
                return True

        return False

    def get_queue(self, queue_id: str) -> Optional[ActiveMatchQueue]:
        """Gets an active queue with the given ID.

        Args:
            queue_id (str): The queue to retrieve.

        Returns:
            Optional[ActiveMatchQueue]: The active queue if exists, None otherwise.
        """
        for active_queue in self.active_queues:
            if active_queue.queue.queue_id == queue_id:
                return active_queue

        return None

    def get_active_match(self, bot_match_id: int) -> Optional[ActiveMatch]:
        """Gets an active match with the given bot match ID.

        Args:
            bot_match_id (int): The match to retrieve.

        Returns:
            Optional[ActiveMatch]: The active match if exists, None otherwise.
        """
        for active_match in self.active_matches:
            if active_match.bot_match_id == bot_match_id:
                return active_match

        return None

    def is_player_in_match(self, player: PlayerProfile) -> bool:
        """Checks if a player is in an active match.

        Args:
            player (PlayerProfile): The player to check.

        Returns:
            bool: True if player is in an active match, False otherwise.
        """
        for match in self.active_matches:
            if match.has_player(player):
                return True

        return False

    def find_match_with_player(self, player: PlayerProfile) -> ActiveMatch | None:
        """Finds an ActiveMatch with a specific player as participant

        Args:
            player (PlayerProfile): The player to find in a match.

        Returns:
            ActiveMatch: Active match record if the player is in a match, None otherwise
        """
        for match in self.active_matches:
            if match.has_player(player):
                return match

        return None

    def add_party_to_queue(
        self, players: List[PlayerProfile], queue_id: str
    ) -> Optional[ActiveMatchQueue]:
        """Adds a list of players (1+) to a queue as a party, meaning they will
            join matches together (as a team) and be removed from queue together.

        Args:
            players: (List[PlayerProfile]): The players to add as a party.
            queue_id (str): The queue to add party to.

        Returns:
            Optional[ActiveMatchQueue]: Returns the queue the party was added to, None if not.
        """
        queue = self.get_queue(queue_id)
        if queue is None:
            return None

        # Ensure none of the players are still in a match
        for player in players:
            if self.is_player_in_match(player):
                return None

        # Ensure this queue will allow this party to join
        if not queue.can_add_party(players):
            return None

        # Add party to queue
        party_added = queue.add_party(players)
        if not party_added:
            return None

        self.mm_event_bus.add_queue_update(queue.queue.queue_id)

        self.maybe_publish_queue_started_message(players[0], queue)

        # Update this here so that only periods of no parties joining for >1hr will ping
        self._last_queue_started_time[queue.queue.queue_id] = time.time()

        return queue

    def remove_party_from_queue(
        self, players: List[PlayerProfile], queue_id: str
    ) -> None:
        """Removes a list of players (1+) from a queue, assuming they are a party.
            If they disbanded or are not a party, this method will remove all players anyway.

        Args:
            players (List[PlayerProfile]): The players to remove from the queue.
            queue_id (str): The queue to remove the players from.
        """
        queue = self.get_queue(queue_id)
        if queue is None:
            return

        queue.remove_party(players)

        self.mm_event_bus.add_player_left_queue(queue_id, players)

    def remove_all_parties_from_queue(self, queue_id: str) -> List[PlayerProfile]:
        """Removes all parties from a queue.

        Args:
            queue_id (str): The queue to remove all parties from.
        """
        queue = self.get_queue(queue_id)
        if queue is None:
            return []

        kicked_players = queue.kick_all_players_from_queue()
        self.mm_event_bus.add_player_left_queue(queue.queue.queue_id, kicked_players)
        return kicked_players

    def remove_party_from_all_queues(
        self,
        players: List[PlayerProfile],
    ) -> None:
        """Removes a list of players from all queues they are in, and returns the list of queues.

        Args:
            players (List[PlayerProfile]): The players to remove from all queues.
        """
        for active_queue in self.active_queues:
            self.remove_party_from_queue(players, active_queue.queue.queue_id)

    def cancel_match(self, bot_match_id: int) -> Optional[ActiveMatch]:
        """Cancels an active match with the given bot match ID, if one exists.

        Args:
            bot_match_id (int): The bot match ID of the match to cancel.

        Returns:
            Optional[ActiveMatch]: The canceled match if existed, None otherwise.
        """
        match = self.get_active_match(bot_match_id)
        if match is None:
            return None

        # Complete the match
        self.active_matches.remove(match)
        canceled_match = CompletedMatch(match, canceled=True)
        self.mm_event_bus.add_new_completed_match(canceled_match)
        canceled_match.cleanup()

        return match

    def remove_player_from_all_active_queues(self, player: PlayerProfile) -> None:
        """Removes a player from all queues they are in.

        Args:
            player (PlayerProfile): The player to remove.
        """
        for active_queue in self.active_queues:
            active_queue.remove_party([player])

    async def upload_match_results_and_cleanup_event(
        self, match: CompletedMatch
    ) -> None:
        """Uploads match results to DDB and deletes the match from Nadeo's servers.

        Args:
            match (CompletedMatch): The completed match to cleanup.
        """
        logging.debug(
            f"Uploading match results for match {match.active_match.match_id} and "
            f"deleting event {match.active_match.event_id}..."
        )

        self.ddb_manager.put_match_results(
            match.active_match.bot_match_id,
            match.active_match.match_queue.queue_id,
            match.active_match.match_id,
            match.active_match.match_live_id,
            match.time_completed,
            match.match_results.__str__(),
        )

        for player in match.active_match.participants():
            player_pos = match.match_results.get_rank(player.tm_account_id)
            if player_pos is None:
                logging.warning(
                    f"Could not find player position for player {player.tm_account_id} "
                    f"in match {match.active_match.match_id}."
                )
                continue
            player_won = True if player_pos == 1 else False

            self.ddb_manager.update_player_matches_played(
                player.tm_account_id,
                match.active_match.match_queue.queue_id,
                player_won,
            )

        match.cleanup()

    async def calculate_elos_and_upload(
        self, match: CompletedMatch
    ) -> Dict[PlayerProfile, Dict[str, tuple[int, int]]]:
        """Calculates elo for each player in the match, persists to DDB, and returns a mapping
            of players to their respective gained elo on each leaderboard.

        Args:
            match (CompletedMatch): The completed match to calculate elo from.

        Returns:
            Dict[PlayerProfile, Dict[str, tuple[int, int]]]: A mapping of players
            to their respective changed elo on each leaderboard.
        """
        if isinstance(match.active_match.player_profiles, List):
            match_players = match.active_match.player_profiles
        else:
            match_players = match.active_match.player_profiles.players()

        # Create a mapping from player profile -> dict of leaderboard id -> (updated elo, elo diff)
        player_profile_to_leaderboard_elo_update_and_diff_map: Dict[
            PlayerProfile, Dict[str, tuple[int, int]]
        ] = {}

        for player_profile in match_players:
            leaderboards_to_elo_update_and_diff_map: Dict[str, tuple[int, int]] = {}
            for leaderboard_id in match.active_match.match_queue.leaderboard_ids:  # type: ignore
                # Find the updated elo rating for this player on this leaderboard
                updated_elo = None
                for updated_elo_rating in match.updated_elo_ratings:
                    if (
                        updated_elo_rating.tm_account_id == player_profile.tm_account_id
                        and updated_elo_rating.leaderboard_id == leaderboard_id
                    ):
                        updated_elo = updated_elo_rating.elo
                elo_diff = None
                for elo_diff_rating in match.elo_differences:
                    if (
                        elo_diff_rating.tm_account_id == player_profile.tm_account_id
                        and elo_diff_rating.leaderboard_id == leaderboard_id
                    ):
                        elo_diff = elo_diff_rating.elo

                if updated_elo is None or elo_diff is None:
                    logging.error(
                        f"Could not find updated elo or elo diff for player {player_profile.tm_account_id} "
                        f"on leaderboard {leaderboard_id}"
                    )
                    continue
                leaderboards_to_elo_update_and_diff_map[leaderboard_id] = (
                    updated_elo,
                    elo_diff,
                )

            # Add all the leaderboards' updated elos and differences to the map
            player_profile_to_leaderboard_elo_update_and_diff_map[player_profile] = (
                leaderboards_to_elo_update_and_diff_map
            )

        # Now add the updated elos back to the elo table for each leaderboard
        for (
            player_profile,
            updated_elos_by_leaderboard_id,
        ) in player_profile_to_leaderboard_elo_update_and_diff_map.items():
            for leaderboard_id, (
                updated_elo,
                elo_diff,
            ) in updated_elos_by_leaderboard_id.items():
                self.ddb_manager.update_player_elo(
                    player_profile.tm_account_id, leaderboard_id, updated_elo
                )

        return player_profile_to_leaderboard_elo_update_and_diff_map

    async def update_player_rank_role(
        self,
        player_profile: PlayerProfile,
        updated_elos_by_leaderboard_id: Dict[str, tuple[int, int]],
        global_leaderboard: str,
    ) -> None:
        """Updates a player's rank role in discord if they have surpassed a new minimum elo or
            dropped below a previous minimum elo.

        Args:
            player_profile (PlayerProfile): Player to update the rank role for.
            updated_elos_by_leaderboard_id (Dict[str, tuple[int, int]]): A mapping of leaderboard IDs
                to a player's updated elo and elo diff from the latest match.
        """
        try:
            # NOTE we are operating under the assumption this bot is only connected to one server
            guild = self.bot.guilds[0]
            member = guild.get_member(player_profile.discord_account_id)

            if not member:
                logging.error(
                    f"Could not find member with ID {player_profile.discord_account_id} in any "
                    f"of the guilds the bot is connected to."
                )
                return

            member_roles = member.roles
        except Exception as e:
            logging.error(f"Error getting member roles: {e}")
            return

        player_elo_update = updated_elos_by_leaderboard_id.get(global_leaderboard)  # type: ignore
        if player_elo_update is None:
            logging.error(
                f"Could not find player elo for global leaderboard {global_leaderboard}"
            )
            return

        player_elo = player_elo_update[0]
        rank_roles = self.ddb_manager.get_rank_roles()

        # Find the rank role the user should have now
        new_rank_role = None
        distance_above_min_elo = 0
        for role in rank_roles:
            if player_elo - role.min_elo > distance_above_min_elo:
                distance_above_min_elo = player_elo - role.min_elo
                new_rank_role = role

        if new_rank_role is None:
            logging.warning(
                f"Could not find new rank role for player elo {player_elo}."
            )
            return

        # Remove user's discord roles which correspond to a rank role
        rank_role_ids = [role.rank_role_id for role in rank_roles]
        for role in member_roles:
            if role.id in rank_role_ids:  # type: ignore
                await member.remove_roles(role)

        # Add the new role to the user
        await member.add_roles(guild.get_role(new_rank_role.rank_role_id))  # type: ignore
        logging.info(
            f"Updated rank role for user {player_profile.discord_account_id} to "
            f"{new_rank_role.display_name}"
        )  # type: ignore

    async def send_players_match_complete_notification(
        self,
        bot_match_id: int,
        player_profile_to_leaderboard_elo_update_and_diff_map: Dict[
            PlayerProfile, Dict[str, tuple[int, int]]
        ],
    ) -> None:
        """Sends players from a match the complete notification with their updated elo and
        difference for each leaderboard the match queue is in.

        Args:
            bot_match_id (int): The bot match ID completed.
            player_profile_to_leaderboard_elo_update_and_diff_map
                (Dict[PlayerProfile, Dict[str, tuple[int, int]]]): A dictionary mapping players
                to a map of leaderboard ID to a tuple of player elo and elo difference.
        """
        try:
            ping_channel = await get_ping_channel(self.bot, self.s3_manager)

            if not ping_channel:
                logging.warning("No ping channel found.")
                return

            players = list(player_profile_to_leaderboard_elo_update_and_diff_map.keys())
            content = ""
            for player in players:
                content += f"<@{player.discord_account_id}> "

            value = "Updated elos have been calculated:\n"
            value += "-----------------------------------------\n"
            for (
                player,
                leaderboard_to_elos,
            ) in player_profile_to_leaderboard_elo_update_and_diff_map.items():
                value += f"<@{player.discord_account_id}>\n"
                for leaderboard, (updated_elo, elo_diff) in leaderboard_to_elos.items():
                    elo_diff_prefix = "+" if elo_diff >= 0 else ""
                    value += (
                        f"{leaderboard}: {updated_elo} ({elo_diff_prefix}{elo_diff})\n"
                    )
                value += "-----------------------------------------\n"

            embed = discord.Embed(color=COLOR_EMBED, timestamp=datetime.utcnow())
            embed.add_field(name=f"❗ Match Finished - #{bot_match_id}", value=value)

            await ping_channel.send(content=content, embed=embed)
        except Exception as e:
            logging.error(f"Error sending message to {player.discord_account_id}: {e}")

    def maybe_publish_queue_started_message(
        self, player: PlayerProfile, queue: ActiveMatchQueue
    ) -> None:
        """Checks if a player has joined the queue after sufficient time of inactivity. If so,
            publish a message that the queue has started.

        Args:
            added_player (PlayerProfile): The player who joined the queue.
            queue (ActiveMatchQueue): The queue to check if should ping for.
        """
        time_of_last_ping = self._last_queue_started_time.get(queue.queue.queue_id)
        now = time.time()

        if len(queue.player_parties) == 1 and (
            time_of_last_ping is None
            or now - time_of_last_ping
            > QUEUE_MANAGER_MIN_TIME_PING_FIRST_PLAYER_JOIN_QUEUE_SEC
        ):
            logging.info(
                f"First player {player} joined queue {queue.queue.queue_id}, triggering queue-started message"
            )
            self.mm_event_bus.add_new_queue_started(queue.queue.queue_id, player)

    @tasks.loop(seconds=CHECK_QUEUES_TO_SPAWN_NEW_MATCH_TASK_SEC)
    async def check_queues_to_spawn_new_match(self):
        """Checks all active queues and spawns a new match if appropriate."""
        logging.debug("Checking queues to spawn new match...")
        for active_queue in self.active_queues:
            try:
                should_generate_match = active_queue.should_generate_match()
                if not should_generate_match:
                    continue
            except Exception as e:
                logging.error(f"Error checking queues to spawn new match: {e}")
                continue

            try:
                bot_match_id = self.ddb_manager.get_next_bot_match_id_and_increment()
                active_match = await active_queue.generate_match(bot_match_id)
            except Exception as e:
                logging.error(
                    f"Error generating match {bot_match_id} for active queue {active_queue}: {e}"
                )
                bot_ping_channel = await get_ping_channel(self.bot, self.s3_manager)
                # If the error is a CreateMatchError, Nadeo is taking too long to respond and we
                # don't want to disable our queue sinc it's not a bug in our code.
                if isinstance(e, CreateMatchError):
                    logging.info(
                        f"Not disabling queue {active_queue.queue.queue_id} because it is a CreateMatchError."
                    )
                    # Kick all players from the queue
                    kicked_players = self.remove_all_parties_from_queue(
                        active_queue.queue.queue_id
                    )
                    if bot_ping_channel is not None:
                        players_str = ", ".join(
                            f"<@{player.discord_account_id}>"
                            for player in kicked_players
                        )
                        await bot_ping_channel.send(
                            f"Queue {active_queue.queue.queue_id} is taking too long to generate a match. "
                            f"Kicking players: {players_str}."
                        )
                    continue
                # Any other type of error - report it and disable the queue
                # Remove from active queues so we don't keep retrying with failures
                self.active_queues.remove(active_queue)
                # Notify players/mods in bot ping channel.
                if bot_ping_channel is not None:
                    await bot_ping_channel.send(
                        f"Error generating match {bot_match_id} for "
                        f"active queue {active_queue}. Disabling it temporarily."
                    )
                continue

            logging.info(
                f"Match generated for queue {active_queue.queue.queue_id}, match id {active_match.match_id}."
            )

            # Remove all players in this match from every other queue
            for player in active_match.participants():
                self.remove_player_from_all_active_queues(player)

            # Persist the match in the case of bot going down
            persist_match(active_match)

            # Distribute the match to whom it may concern
            self.mm_event_bus.add_new_active_match(active_match)

            # Add to active matches to be monitored
            self.active_matches.append(active_match)

    @tasks.loop(seconds=CHECK_ACTIVE_MATCHES_FINISHED_TASK_SEC)
    async def check_active_matches_to_complete(self):
        """Checks if matches have finished to complete them by deleting and distributing elo."""
        logging.debug("Checking active matches to complete...")
        for active_match in self.active_matches:
            try:
                if not active_match.is_match_complete():
                    continue

                # Complete the match
                completed_match = CompletedMatch(active_match)
                self.active_matches.remove(active_match)

                # Handle remote match completion (AWS + Nadeo services)
                await self.upload_match_results_and_cleanup_event(completed_match)

                # Handle elo calculation
                player_profile_to_leaderboard_elo_update_and_diff_map = (
                    await self.calculate_elos_and_upload(completed_match)
                )

                # Update players' rank roles if there's a global leaderboard
                configs = self.s3_manager.get_configs()
                global_leaderboard = configs.global_leaderboard_id
                if global_leaderboard is None:
                    logging.debug(
                        "No global leaderboard configured, skipping rank role updates."
                    )
                else:
                    for (
                        player_profile,
                        updated_elos_by_leaderboard_id,
                    ) in player_profile_to_leaderboard_elo_update_and_diff_map.items():
                        await self.update_player_rank_role(
                            player_profile,
                            updated_elos_by_leaderboard_id,
                            global_leaderboard,
                        )

                # Notify players of match completion with info on results
                await self.send_players_match_complete_notification(
                    completed_match.active_match.bot_match_id,
                    player_profile_to_leaderboard_elo_update_and_diff_map,
                )

                # Distribute the completed match to whom it may concern
                self.mm_event_bus.add_new_completed_match(completed_match)

            except Exception as e:
                logging.error(f"Error checking active matches to complete: {e}")

    @tasks.loop(seconds=CHECK_KICK_QUEUED_PLAYERS_TASK_SEC)
    async def check_kick_queued_players(self):
        """Checks if players have been queued for too long and kicks them."""
        logging.debug("Checking queued players to kick...")
        now = time.time()
        for active_queue in self.active_queues:
            for queued_party in active_queue.player_parties:
                if (
                    now - queued_party.queue_join_time()
                    > MAX_TIME_BEFORE_KICK_PLAYER_QUEUE_SEC
                ):
                    self.remove_party_from_queue(
                        queued_party.players(), active_queue.queue.queue_id
                    )
                    logging.info(
                        f"Kicked players {queued_party.players()} from {active_queue.queue.queue_id} queue "
                        f"for exceeding {MAX_TIME_BEFORE_KICK_PLAYER_QUEUE_SEC} seconds in queue."
                    )

    @check_queues_to_spawn_new_match.before_loop
    @check_active_matches_to_complete.before_loop
    @check_kick_queued_players.before_loop
    async def before_checks(self):
        """Wait until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(MatchmakingManagerV2(bot))


def get_matchmaking_manager_v2() -> Optional[MatchmakingManagerV2]:
    """Gets matchmaking manager singleton if initialized, else returns None."""
    return registry.get(COG_MATCHMAKING_MANAGER_V2)

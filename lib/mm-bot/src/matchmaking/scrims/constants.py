SCRIM_MAX_PLAYERS = 4
SCRIM_TEAM_SIZE = 2

# Prefix for the in-memory queue ID of each scrim room
SCRIM_QUEUE_ID_PREFIX = "scrim-"

SCRIM_CHANNEL_NAME_PREFIX = "scrim-"
# Marks a channel as a scrim room, so rooms left over from a previous bot instance can be cleaned up
SCRIM_ROOM_CHANNEL_TOPIC = (
    "Better Matchmaking scrim room. It is deleted when the room closes."
)

SCRIM_INVITE_EXPIRATION_SEC = 5 * 60
SCRIM_ROOM_INACTIVITY_SEC = 30 * 60

SCRIM_CHECK_ROOMS_TASK_SEC = 30
SCRIM_CHECK_COMPLETED_MATCHES_TASK_SEC = 5
